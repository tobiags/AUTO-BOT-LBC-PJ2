import json
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import boundaries
from app.config import get_settings
from app.db import get_db
from app.models import (
    ApifyAccountCreate,
    ApifyAccountOut,
    ApifyBindingCreate,
    ApifyBindingOut,
    ApifyCatalogResource,
    CampaignStatus,
)
from app.services.apify_secrets import ApifySecretCodec
from app.tables import (
    ApifyAccount,
    ApifyActorBinding,
    AuditEvent,
    Campaign,
    Sector,
    Workspace,
)


def _codec() -> ApifySecretCodec:
    settings = get_settings()
    return ApifySecretCodec(
        settings.apify_token_encryption_key,
        settings.secret_key,
    )


async def _workspace(db: AsyncSession) -> Workspace:
    workspace = await db.scalar(select(Workspace).order_by(Workspace.created_at).limit(1))
    if workspace is None:
        workspace = Workspace(name="AutoTransfert")
        db.add(workspace)
        await db.flush()
    return workspace


def _audit(
    db: AsyncSession,
    *,
    action: str,
    target_type: str,
    target_id: str,
    summary: dict | None = None,
    status: str = "success",
) -> None:
    db.add(
        AuditEvent(
            actor="system",
            role="admin",
            action=action,
            target_type=target_type,
            target_id=target_id,
            input_summary=summary,
            result_status=status,
        )
    )


def _account_output(row: ApifyAccount) -> ApifyAccountOut:
    token = _codec().decrypt(row.token_ciphertext)
    return ApifyAccountOut(
        id=row.id,
        workspace_id=row.workspace_id,
        label=row.label,
        apify_user_id=row.apify_user_id,
        username=row.username,
        token_masked=ApifySecretCodec.mask(token),
        status=row.status,
        last_checked_at=row.last_checked_at,
        last_error=row.last_error,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def create_account(payload: ApifyAccountCreate) -> ApifyAccountOut:
    token = payload.token.get_secret_value()
    identity = await boundaries.apify_validate_token(token)
    codec = _codec()
    fingerprint = codec.fingerprint(token)
    webhook_secret = secrets.token_urlsafe(32)

    async with get_db() as db:
        workspace = await _workspace(db)
        duplicate = await db.scalar(
            select(ApifyAccount).where(
                ApifyAccount.workspace_id == workspace.id,
                ApifyAccount.token_fingerprint == fingerprint,
            )
        )
        if duplicate is not None:
            raise ValueError("apify_token_already_registered")
        row = ApifyAccount(
            workspace_id=workspace.id,
            label=payload.label.strip(),
            apify_user_id=str(identity["id"]),
            username=str(identity.get("username") or identity["id"]),
            token_ciphertext=codec.encrypt(token),
            token_fingerprint=fingerprint,
            webhook_secret_ciphertext=codec.encrypt(webhook_secret),
            webhook_secret_hash=codec.fingerprint(webhook_secret),
            last_checked_at=datetime.now(UTC),
        )
        db.add(row)
        await db.flush()
        _audit(
            db,
            action="apify.account.create",
            target_type="apify_account",
            target_id=str(row.id),
            summary={"label": row.label, "username": row.username},
        )
        return _account_output(row)


async def list_accounts() -> list[ApifyAccountOut]:
    async with get_db() as db:
        workspace = await _workspace(db)
        rows = list(
            (
                await db.scalars(
                    select(ApifyAccount)
                    .where(ApifyAccount.workspace_id == workspace.id)
                    .order_by(ApifyAccount.created_at)
                )
            ).all()
        )
        return [_account_output(row) for row in rows]


async def replace_account_token(account_id: UUID, token: str) -> ApifyAccountOut:
    identity = await boundaries.apify_validate_token(token)
    codec = _codec()
    fingerprint = codec.fingerprint(token)
    async with get_db() as db:
        row = await db.get(ApifyAccount, account_id)
        if row is None:
            raise LookupError("apify_account_not_found")
        duplicate = await db.scalar(
            select(ApifyAccount).where(
                ApifyAccount.workspace_id == row.workspace_id,
                ApifyAccount.token_fingerprint == fingerprint,
                ApifyAccount.id != row.id,
            )
        )
        if duplicate is not None:
            raise ValueError("apify_token_already_registered")
        row.token_ciphertext = codec.encrypt(token)
        row.token_fingerprint = fingerprint
        row.apify_user_id = str(identity["id"])
        row.username = str(identity.get("username") or identity["id"])
        row.status = "active"
        row.last_checked_at = datetime.now(UTC)
        row.last_error = None
        _audit(
            db,
            action="apify.account.token.replace",
            target_type="apify_account",
            target_id=str(row.id),
        )
        await db.flush()
        return _account_output(row)


async def suspend_account(account_id: UUID) -> ApifyAccountOut:
    async with get_db() as db:
        row = await db.get(ApifyAccount, account_id)
        if row is None:
            raise LookupError("apify_account_not_found")
        row.status = "suspended"
        _audit(
            db,
            action="apify.account.suspend",
            target_type="apify_account",
            target_id=str(row.id),
        )
        await db.flush()
        return _account_output(row)


async def delete_account(account_id: UUID) -> None:
    codec = _codec()
    async with get_db() as db:
        row = await db.get(ApifyAccount, account_id)
        if row is None:
            raise LookupError("apify_account_not_found")
        token = codec.decrypt(row.token_ciphertext)
        webhook_ids = list(
            (
                await db.scalars(
                    select(ApifyActorBinding.webhook_id).where(
                        ApifyActorBinding.account_id == account_id,
                        ApifyActorBinding.webhook_id.is_not(None),
                    )
                )
            ).all()
        )

    try:
        for webhook_id in webhook_ids:
            await boundaries.apify_delete_webhook(token, webhook_id)
    except Exception as exc:
        async with get_db() as db:
            row = await db.get(ApifyAccount, account_id)
            if row is not None:
                row.status = "suspended"
                row.last_error = str(exc)[:500]
                _audit(
                    db,
                    action="apify.account.delete",
                    target_type="apify_account",
                    target_id=str(account_id),
                    status="retryable_error",
                )
        raise RuntimeError("apify_webhook_delete_retryable") from exc

    async with get_db() as db:
        row = await db.get(ApifyAccount, account_id)
        if row is None:
            return
        _audit(
            db,
            action="apify.account.delete",
            target_type="apify_account",
            target_id=str(account_id),
        )
        await db.delete(row)


def _catalog_resource(resource_type: str, item: dict) -> ApifyCatalogResource:
    resource_id = str(item.get("id") or item.get("name") or "")
    if not resource_id:
        raise ValueError("apify_catalog_resource_without_id")
    return ApifyCatalogResource(
        resource_type=resource_type,
        resource_id=resource_id,
        name=str(item.get("title") or item.get("name") or resource_id),
        description=item.get("description"),
        modified_at=item.get("modifiedAt"),
    )


async def _remote_catalog(account: ApifyAccount) -> list[ApifyCatalogResource]:
    token = _codec().decrypt(account.token_ciphertext)
    actors = await boundaries.apify_list_actors(token)
    tasks = await boundaries.apify_list_tasks(token)
    return [
        *(_catalog_resource("actor", item) for item in actors),
        *(_catalog_resource("task", item) for item in tasks),
    ]


async def sync_catalog(account_id: UUID) -> list[ApifyCatalogResource]:
    async with get_db() as db:
        row = await db.get(ApifyAccount, account_id)
        if row is None:
            raise LookupError("apify_account_not_found")
        catalog = await _remote_catalog(row)
        row.last_checked_at = datetime.now(UTC)
        row.last_error = None
        _audit(
            db,
            action="apify.catalog.sync",
            target_type="apify_account",
            target_id=str(account_id),
            summary={"resources": len(catalog)},
        )
        return catalog


def _binding_output(row: ApifyActorBinding) -> ApifyBindingOut:
    return ApifyBindingOut.model_validate(row)


async def _resolve_sector(
    db: AsyncSession,
    binding: ApifyActorBinding,
    campaign: Campaign,
) -> None:
    if binding.sector_id is not None:
        sector = await db.get(Sector, binding.sector_id)
        if (
            sector is None
            or sector.workspace_id != binding.workspace_id
            or sector.status != "actif"
        ):
            raise ValueError("sector_required")
        return

    criteria = campaign.search_criteria or {}
    query = select(Sector).where(
        Sector.workspace_id == binding.workspace_id,
        Sector.status == "actif",
    )
    department = criteria.get("department")
    region = criteria.get("region")
    if department:
        query = query.where(Sector.department == str(department))
    elif region:
        query = query.where(Sector.region == str(region))
    sector = await db.scalar(query.order_by(Sector.created_at).limit(1))
    if sector is None:
        raise ValueError("sector_required")
    binding.sector_id = sector.id


async def _validate_binding_activation(
    db: AsyncSession,
    binding: ApifyActorBinding,
) -> ApifyAccount:
    account = await db.get(ApifyAccount, binding.account_id)
    if account is None or account.status != "active":
        raise ValueError("apify_account_not_active")
    campaign = await db.get(Campaign, binding.campaign_id)
    if campaign is None or campaign.status not in {
        CampaignStatus.RUNNING,
        CampaignStatus.RUNNING.value,
    }:
        raise ValueError("campaign_not_running")
    if binding.schedule_authority == "internal" and binding.schedule_minutes is None:
        raise ValueError("invalid_scheduling_authority")
    if binding.schedule_authority == "apify" and binding.schedule_minutes is not None:
        raise ValueError("invalid_scheduling_authority")
    await _resolve_sector(db, binding, campaign)
    catalog = await _remote_catalog(account)
    if not any(
        resource.resource_type.value == binding.resource_type
        and resource.resource_id == binding.resource_id
        for resource in catalog
    ):
        raise ValueError("resource_not_in_catalog")
    return account


async def _create_binding_webhook(
    account: ApifyAccount,
    binding: ApifyActorBinding,
) -> str:
    settings = get_settings()
    if not settings.apify_webhook_base_url:
        raise ValueError("apify_webhook_url_required")
    codec = _codec()
    token = codec.decrypt(account.token_ciphertext)
    secret = codec.decrypt(account.webhook_secret_ciphertext)
    url = (
        f"{settings.apify_webhook_base_url.rstrip('/')}"
        f"/webhooks/apify/{account.id}"
    )
    result = await boundaries.apify_create_webhook(
        token,
        binding.resource_type,
        binding.resource_id,
        url,
        secret,
    )
    return str(result["id"])


async def create_binding(payload: ApifyBindingCreate) -> ApifyBindingOut:
    codec = _codec()
    async with get_db() as db:
        account = await db.get(ApifyAccount, payload.account_id)
        if account is None:
            raise LookupError("apify_account_not_found")
        binding = ApifyActorBinding(
            workspace_id=account.workspace_id,
            account_id=account.id,
            sector_id=payload.sector_id,
            campaign_id=payload.campaign_id,
            resource_type=payload.resource_type,
            resource_id=payload.resource_id,
            name=payload.name or payload.resource_id,
            input_ciphertext=codec.encrypt(
                json.dumps(payload.input, sort_keys=True, separators=(",", ":"))
            ),
            schedule_authority=payload.schedule_authority,
            schedule_minutes=payload.schedule_minutes,
            enabled=False,
            next_run_at=(
                datetime.now(UTC) + timedelta(minutes=payload.schedule_minutes)
                if payload.schedule_authority == "internal"
                and payload.schedule_minutes is not None
                else None
            ),
        )
        db.add(binding)
        await _validate_binding_activation(db, binding)
        await db.flush()
        _audit(
            db,
            action="apify.binding.create",
            target_type="apify_binding",
            target_id=str(binding.id),
            summary={
                "resource_type": binding.resource_type,
                "resource_id": binding.resource_id,
            },
        )
        return _binding_output(binding)


async def list_bindings() -> list[ApifyBindingOut]:
    async with get_db() as db:
        workspace = await _workspace(db)
        rows = list(
            (
                await db.scalars(
                    select(ApifyActorBinding)
                    .where(ApifyActorBinding.workspace_id == workspace.id)
                    .order_by(ApifyActorBinding.created_at)
                )
            ).all()
        )
        return [_binding_output(row) for row in rows]


async def update_binding(
    binding_id: UUID,
    payload: ApifyBindingCreate,
) -> ApifyBindingOut:
    codec = _codec()
    async with get_db() as db:
        binding = await db.get(ApifyActorBinding, binding_id)
        if binding is None:
            raise LookupError("apify_binding_not_found")
        old_account = await db.get(ApifyAccount, binding.account_id)
        if old_account is None:
            raise LookupError("apify_account_not_found")
        if binding.enabled and binding.webhook_id:
            token = codec.decrypt(old_account.token_ciphertext)
            await boundaries.apify_delete_webhook(token, binding.webhook_id)
            binding.webhook_id = None

        account = await db.get(ApifyAccount, payload.account_id)
        if account is None or account.workspace_id != binding.workspace_id:
            raise LookupError("apify_account_not_found")
        binding.account_id = account.id
        binding.sector_id = payload.sector_id
        binding.campaign_id = payload.campaign_id
        binding.resource_type = payload.resource_type
        binding.resource_id = payload.resource_id
        binding.name = payload.name or payload.resource_id
        binding.input_ciphertext = codec.encrypt(
            json.dumps(payload.input, sort_keys=True, separators=(",", ":"))
        )
        binding.schedule_authority = payload.schedule_authority
        binding.schedule_minutes = payload.schedule_minutes
        binding.next_run_at = (
            datetime.now(UTC) + timedelta(minutes=payload.schedule_minutes)
            if payload.schedule_authority == "internal"
            and payload.schedule_minutes is not None
            else None
        )
        validated_account = await _validate_binding_activation(db, binding)
        if binding.enabled:
            binding.webhook_id = await _create_binding_webhook(
                validated_account, binding
            )
        _audit(
            db,
            action="apify.binding.update",
            target_type="apify_binding",
            target_id=str(binding.id),
        )
        await db.flush()
        return _binding_output(binding)


async def set_binding_enabled(binding_id: UUID, enabled: bool) -> ApifyBindingOut:
    async with get_db() as db:
        binding = await db.get(ApifyActorBinding, binding_id)
        if binding is None:
            raise LookupError("apify_binding_not_found")
        if binding.enabled == enabled:
            return _binding_output(binding)
        account = await db.get(ApifyAccount, binding.account_id)
        if account is None:
            raise LookupError("apify_account_not_found")
        if enabled:
            account = await _validate_binding_activation(db, binding)
            binding.webhook_id = await _create_binding_webhook(account, binding)
            binding.enabled = True
        else:
            if binding.webhook_id:
                token = _codec().decrypt(account.token_ciphertext)
                await boundaries.apify_delete_webhook(token, binding.webhook_id)
            binding.webhook_id = None
            binding.enabled = False
        _audit(
            db,
            action="apify.binding.enable" if enabled else "apify.binding.disable",
            target_type="apify_binding",
            target_id=str(binding.id),
        )
        await db.flush()
        return _binding_output(binding)
