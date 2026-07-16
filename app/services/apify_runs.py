import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app import boundaries
from app.db import get_db
from app.models import ApifyRunOut, ApifyWebhookPayload
from app.services.apify_secrets import ApifySecretCodec
from app.tables import (
    ApifyAccount,
    ApifyActorBinding,
    ApifyRun,
    AuditEvent,
    WebhookEvent,
)


def _codec() -> ApifySecretCodec:
    from app.config import get_settings

    settings = get_settings()
    return ApifySecretCodec(settings.apify_token_encryption_key, settings.secret_key)


def _run_output(row: ApifyRun) -> ApifyRunOut:
    return ApifyRunOut.model_validate(row)


def _remote_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


async def _binding_for_remote(
    db: AsyncSession,
    account_id: UUID,
    remote: dict,
) -> ApifyActorBinding:
    local_binding_id = remote.get("_binding_id")
    if local_binding_id:
        binding = await db.get(ApifyActorBinding, UUID(str(local_binding_id)))
        if binding is not None and binding.account_id == account_id:
            return binding
    resource_id = remote.get("actorTaskId") or remote.get("actorId") or remote.get("actId")
    query = select(ApifyActorBinding).where(ApifyActorBinding.account_id == account_id)
    if resource_id:
        query = query.where(ApifyActorBinding.resource_id == str(resource_id))
    binding = await db.scalar(
        query.order_by(ApifyActorBinding.enabled.desc(), ApifyActorBinding.created_at).limit(1)
    )
    if binding is None:
        raise ValueError("apify_binding_not_found_for_run")
    return binding


async def _sync_remote_run_in_session(
    db: AsyncSession,
    account: ApifyAccount,
    remote: dict,
) -> ApifyRun:
    remote_run_id = str(remote.get("id") or "")
    if not remote_run_id:
        raise ValueError("apify_remote_run_id_required")
    row = await db.scalar(
        select(ApifyRun).where(
            ApifyRun.account_id == account.id,
            ApifyRun.apify_run_id == remote_run_id,
        )
    )
    if row is None:
        binding = await _binding_for_remote(db, account.id, remote)
        row = ApifyRun(
            workspace_id=account.workspace_id,
            account_id=account.id,
            binding_id=binding.id,
            apify_run_id=remote_run_id,
        )
        db.add(row)
    row.status = str(remote.get("status") or row.status)
    row.started_at = _remote_datetime(remote.get("startedAt")) or row.started_at
    row.finished_at = _remote_datetime(remote.get("finishedAt")) or row.finished_at
    row.default_dataset_id = remote.get("defaultDatasetId") or row.default_dataset_id
    usage = remote.get("usageTotalUsd")
    if usage is not None:
        row.cost_usd = float(usage)
    await db.flush()
    return row


async def sync_remote_run(account_id: UUID, remote: dict) -> ApifyRunOut:
    async with get_db() as db:
        account = await db.get(ApifyAccount, account_id)
        if account is None:
            raise LookupError("apify_account_not_found")
        row = await _sync_remote_run_in_session(db, account, remote)
        return _run_output(row)


async def launch_binding(binding_id: UUID, trigger: str) -> ApifyRunOut:
    original_next_run_at: datetime | None = None
    async with get_db() as db:
        binding = await db.scalar(
            select(ApifyActorBinding)
            .where(ApifyActorBinding.id == binding_id)
            .with_for_update(skip_locked=True)
        )
        if binding is None:
            raise LookupError("apify_binding_not_found_or_locked")
        if not binding.enabled or binding.suspended_reason:
            raise ValueError("apify_binding_not_runnable")
        account = await db.get(ApifyAccount, binding.account_id)
        if account is None or account.status != "active":
            raise ValueError("apify_account_not_active")
        codec = _codec()
        token = codec.decrypt(account.token_ciphertext)
        run_input = json.loads(codec.decrypt(binding.input_ciphertext) or "{}")
        original_next_run_at = binding.next_run_at
        if binding.schedule_authority == "internal" and binding.schedule_minutes:
            binding.next_run_at = datetime.now(UTC) + timedelta(
                minutes=binding.schedule_minutes
            )
        resource_type = binding.resource_type
        resource_id = binding.resource_id
        account_id = account.id

    try:
        remote = await boundaries.apify_start_resource(
            token,
            resource_type,
            resource_id,
            run_input,
        )
    except Exception as exc:
        async with get_db() as db:
            binding = await db.get(ApifyActorBinding, binding_id)
            if binding is not None:
                binding.next_run_at = original_next_run_at
                db.add(
                    AuditEvent(
                        actor="system",
                        role="admin",
                        action="apify.binding.launch",
                        target_type="apify_binding",
                        target_id=str(binding_id),
                        input_summary={"trigger": trigger, "error": str(exc)[:300]},
                        result_status="failed",
                    )
                )
        raise

    remote = dict(remote)
    remote["_binding_id"] = str(binding_id)
    result = await sync_remote_run(account_id, remote)
    async with get_db() as db:
        db.add(
            AuditEvent(
                actor="system",
                role="admin",
                action="apify.binding.launch",
                target_type="apify_binding",
                target_id=str(binding_id),
                input_summary={"trigger": trigger},
                result_status="success",
            )
        )
    return result


async def get_due_binding_ids(now: datetime | None = None) -> list[UUID]:
    current = now or datetime.now(UTC)
    async with get_db() as db:
        return list(
            (
                await db.scalars(
                    select(ApifyActorBinding.id).where(
                        ApifyActorBinding.enabled.is_(True),
                        ApifyActorBinding.schedule_authority == "internal",
                        ApifyActorBinding.next_run_at.is_not(None),
                        ApifyActorBinding.next_run_at <= current,
                        ApifyActorBinding.suspended_reason.is_(None),
                    )
                )
            ).all()
        )


async def get_or_sync_remote_run(
    account_id: UUID,
    remote_run_id: str,
) -> ApifyRunOut:
    async with get_db() as db:
        row = await db.scalar(
            select(ApifyRun).where(
                ApifyRun.account_id == account_id,
                ApifyRun.apify_run_id == remote_run_id,
            )
        )
        if row is not None:
            return _run_output(row)
        account = await db.get(ApifyAccount, account_id)
        if account is None:
            raise LookupError("apify_account_not_found")
        token = _codec().decrypt(account.token_ciphertext)
    remote = await boundaries.apify_get_run(token, remote_run_id)
    if remote is None:
        raise LookupError("apify_remote_run_not_found")
    return await sync_remote_run(account_id, remote)


async def reconcile_runs() -> dict[str, int]:
    async with get_db() as db:
        accounts = list(
            (
                await db.scalars(
                    select(ApifyAccount).where(ApifyAccount.status == "active")
                )
            ).all()
        )
        credentials = [
            (account.id, _codec().decrypt(account.token_ciphertext))
            for account in accounts
        ]
    counters = {"accounts": len(credentials), "runs": 0, "imports_queued": 0}
    for account_id, token in credentials:
        for remote in await boundaries.apify_list_recent_runs(token, limit=100):
            counters["runs"] += 1
            run = await sync_remote_run(account_id, remote)
            if run.status.value == "SUCCEEDED" and run.imported_at is None:
                from app.tasks import import_apify_run_task

                import_apify_run_task.delay(str(account_id), run.apify_run_id)
                counters["imports_queued"] += 1
    return counters


async def replay_run(run_id: UUID) -> dict[str, int]:
    async with get_db() as db:
        row = await db.get(ApifyRun, run_id)
        if row is None:
            raise LookupError("apify_run_not_found")
        if row.status != "SUCCEEDED" or not row.default_dataset_id:
            raise ValueError("apify_run_not_replayable")
        account_id = row.account_id
        remote_run_id = row.apify_run_id
    from app.tasks import import_apify_run_task

    import_apify_run_task.delay(str(account_id), remote_run_id)
    return {"queued": 1}


async def accept_webhook(
    account_id: UUID,
    payload: ApifyWebhookPayload,
    authorization: str | None,
) -> bool:
    resource = payload.resource
    remote_run_id = str(resource.get("id") or "")
    if not remote_run_id:
        raise ValueError("apify_remote_run_id_required")
    async with get_db() as db:
        account = await db.get(ApifyAccount, account_id)
        if account is None:
            raise LookupError("apify_account_not_found")
        expected = f"Bearer {_codec().decrypt(account.webhook_secret_ciphertext)}"
        if authorization is None or not hmac.compare_digest(authorization, expected):
            raise PermissionError("invalid_apify_webhook_secret")
        event_key = hashlib.sha256(
            (
                f"apify:{account_id}:{payload.event_type}:"
                f"{remote_run_id}:{resource.get('status', '')}"
            ).encode()
        ).hexdigest()
        result = await db.execute(
            pg_insert(WebhookEvent)
            .values(
                event_key=event_key,
                source="apify",
                processed=False,
                payload=payload.model_dump(by_alias=True),
            )
            .on_conflict_do_nothing(index_elements=["event_key"])
            .returning(WebhookEvent.id)
        )
        queued = result.scalar() is not None
        if queued:
            await _sync_remote_run_in_session(db, account, resource)
        return queued
