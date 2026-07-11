import asyncio
import hashlib
import uuid
from datetime import UTC, datetime

import phonenumbers
from sqlalchemy import exists, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import get_settings
from app.db import get_db
from app.models import (
    AccountStatus,
    CampaignStatus,
    LbcMessageDirection,
    LbcMessageStatus,
    LbcMessageView,
    ListingSource,
    WorkflowStatus,
)
from app.services.browser_use_cloud import BrowserUseCloudClient
from app.tables import (
    AuditEvent,
    Campaign,
    LbcMessageLog,
    Listing,
    PlatformAccount,
    SmsLog,
    WorkflowRun,
)

LBC_MESSAGE_BATCH_SIZE = 25


def outbound_message_key(campaign_id: str, listing_id: str) -> str:
    digest = hashlib.sha256(f"{campaign_id}:{listing_id}".encode()).hexdigest()[:40]
    return f"outbound:{digest}"


def extract_phone_numbers(text: str) -> list[str]:
    numbers = []
    for match in phonenumbers.PhoneNumberMatcher(text, "FR"):
        if phonenumbers.is_valid_number(match.number):
            formatted = phonenumbers.format_number(
                match.number, phonenumbers.PhoneNumberFormat.E164
            )
            if formatted not in numbers:
                numbers.append(formatted)
    return numbers


async def run_lbc_message_campaign(campaign_id: str, workflow_id: str) -> dict:
    campaign_uuid = uuid.UUID(campaign_id)
    workflow_uuid = uuid.UUID(workflow_id)
    settings = get_settings()
    if not settings.browser_use_api_key:
        raise RuntimeError("Browser Use Cloud is not configured")

    async with get_db() as db:
        campaign = await db.get(Campaign, campaign_uuid)
        workflow = await db.get(WorkflowRun, workflow_uuid)
        if campaign is None or workflow is None:
            raise ValueError("Campaign or workflow not found")
        if campaign.status not in {CampaignStatus.RUNNING, CampaignStatus.PENDING}:
            return {"status": campaign.status.value.lower(), "sent": 0, "failed": 0}
        campaign.status = CampaignStatus.RUNNING
        workflow.status = WorkflowStatus.RUNNING
        workflow.started_at = workflow.started_at or datetime.now(UTC)

        assigned = await db.scalar(
            select(func.count()).select_from(Listing).where(
                Listing.campaign_id == campaign_uuid
            )
        )
        eligible = select(Listing).where(
            Listing.source == ListingSource.LBC,
            ~exists().where(
                (LbcMessageLog.listing_id == Listing.id)
                & (LbcMessageLog.direction == LbcMessageDirection.OUTBOUND)
                & (LbcMessageLog.status.in_([
                    LbcMessageStatus.QUEUED,
                    LbcMessageStatus.SENT,
                ]))
            ),
            ~exists().where(SmsLog.listing_id == Listing.id),
        )
        if assigned:
            eligible = eligible.where(Listing.campaign_id == campaign_uuid)
        listings = (await db.scalars(eligible.limit(LBC_MESSAGE_BATCH_SIZE + 1))).all()
        has_more = len(listings) > LBC_MESSAGE_BATCH_SIZE
        listings = listings[:LBC_MESSAGE_BATCH_SIZE]
        workflow.progress_total = await db.scalar(
            select(func.count()).select_from(eligible.subquery())
        )
        accounts = (
            await db.scalars(
                select(PlatformAccount).where(
                    PlatformAccount.status == AccountStatus.ACTIF,
                    PlatformAccount.browser_use_profile_id.isnot(None),
                )
            )
        ).all()

    if not accounts:
        await _finish_failed(campaign_uuid, workflow_uuid, "No active Browser Use profile")
        return {"status": "paused", "sent": 0, "failed": 0}

    usage = await _today_account_usage()
    sent = 0
    failed = 0
    client = BrowserUseCloudClient(settings.browser_use_api_key)
    for listing in listings:
        if not await _may_continue(campaign_uuid, workflow_uuid):
            break
        account = min(
            (item for item in accounts if usage.get(item.id, 0) < item.quota_actuel),
            key=lambda item: usage.get(item.id, 0),
            default=None,
        )
        if account is None:
            await _pause_for_quota(campaign_uuid, workflow_uuid)
            return {"status": "paused", "sent": sent, "failed": failed}

        message = campaign.message_template.format(
            title=listing.title or "", url=listing.url
        )
        external_key = outbound_message_key(campaign_id, str(listing.id))
        if not await _queue_message(
            external_key, listing.id, account.id, message
        ):
            continue
        try:
            detail = await _send_message_task(
                client, account.browser_use_profile_id, listing.url, message
            )
            if detail.get("isSuccess") is False:
                raise RuntimeError("Browser Use did not confirm message delivery")
            await _mark_message(external_key, LbcMessageStatus.SENT)
            usage[account.id] = usage.get(account.id, 0) + 1
            sent += 1
        except Exception as exc:
            await _mark_message(
                external_key, LbcMessageStatus.FAILED, type(exc).__name__
            )
            failed += 1

    final_status = CampaignStatus.RUNNING if has_more else CampaignStatus.COMPLETED
    async with get_db() as db:
        campaign = await db.get(Campaign, campaign_uuid)
        workflow = await db.get(WorkflowRun, workflow_uuid)
        if campaign.status in {CampaignStatus.PAUSED, CampaignStatus.CANCELLED}:
            final_status = campaign.status
        campaign.status = final_status
        campaign.sent += sent
        campaign.failed += failed
        workflow.progress_current += sent + failed
        workflow.batch_number += 1
        workflow.checkpoint = {
            "channel": "lbc_message",
            "last_batch_sent": sent,
            "last_batch_failed": failed,
            "has_more_backlog": has_more,
        }
        workflow.status = {
            CampaignStatus.RUNNING: WorkflowStatus.RUNNING,
            CampaignStatus.PAUSED: WorkflowStatus.PAUSED,
            CampaignStatus.CANCELLED: WorkflowStatus.CANCELLED,
            CampaignStatus.COMPLETED: WorkflowStatus.COMPLETED,
        }[final_status]
        if workflow.status in {WorkflowStatus.COMPLETED, WorkflowStatus.CANCELLED}:
            workflow.finished_at = datetime.now(UTC)
    return {"status": final_status.value.lower(), "sent": sent, "failed": failed}


async def sync_lbc_inbox(workflow_id: str | None = None) -> dict:
    settings = get_settings()
    if not settings.browser_use_api_key:
        return {"accounts": 0, "received": 0, "phones": 0}
    workflow_uuid = uuid.UUID(workflow_id) if workflow_id else None
    if workflow_uuid:
        async with get_db() as db:
            workflow = await db.get(WorkflowRun, workflow_uuid)
            workflow.status = WorkflowStatus.RUNNING
            workflow.started_at = datetime.now(UTC)
    async with get_db() as db:
        accounts = (
            await db.scalars(
                select(PlatformAccount).where(
                    PlatformAccount.status == AccountStatus.ACTIF,
                    PlatformAccount.browser_use_profile_id.isnot(None),
                )
            )
        ).all()
    client = BrowserUseCloudClient(settings.browser_use_api_key)
    received = 0
    phone_count = 0
    for account in accounts:
        messages = await _fetch_inbox_messages(client, account.browser_use_profile_id)
        for message in messages:
            inserted, phones = await _persist_inbound_message(account.id, message)
            received += int(inserted)
            phone_count += len(phones) if inserted else 0
    result = {"accounts": len(accounts), "received": received, "phones": phone_count}
    if workflow_uuid:
        async with get_db() as db:
            workflow = await db.get(WorkflowRun, workflow_uuid)
            workflow.status = WorkflowStatus.COMPLETED
            workflow.checkpoint = result
            workflow.finished_at = datetime.now(UTC)
    return result


async def list_lbc_messages(limit: int = 100) -> list[LbcMessageView]:
    async with get_db() as db:
        rows = (
            await db.scalars(
                select(LbcMessageLog)
                .order_by(LbcMessageLog.created_at.desc())
                .limit(limit)
            )
        ).all()
    return [LbcMessageView.model_validate(row) for row in rows]


async def queue_inbox_sync(
    *, idempotency_key: str, actor: str, role: str
) -> uuid.UUID:
    async with get_db() as db:
        existing = await db.scalar(
            select(WorkflowRun).where(WorkflowRun.idempotency_key == idempotency_key)
        )
        if existing:
            return existing.id
        workflow = WorkflowRun(
            idempotency_key=idempotency_key,
            workflow_type="messaging.inbox_sync",
            target_type="platform",
            target_id="leboncoin",
            status=WorkflowStatus.PENDING,
            initiated_by=actor,
        )
        db.add(workflow)
        await db.flush()
        db.add(AuditEvent(
            actor=actor, role=role, action="messaging.inbox_sync",
            target_type="platform", target_id="leboncoin",
            idempotency_key=idempotency_key, input_summary=None,
            result_status="queued", workflow_run_id=workflow.id,
        ))
        workflow_id = workflow.id
    from app.tasks import sync_lbc_inbox_task

    task = sync_lbc_inbox_task.delay(str(workflow_id))
    async with get_db() as db:
        workflow = await db.get(WorkflowRun, workflow_id)
        workflow.celery_task_id = task.id
    return workflow_id


async def _fetch_inbox_messages(
    client: BrowserUseCloudClient, profile_id: str
) -> list[dict]:
    schema = {
        "type": "object",
        "properties": {
            "messages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "external_key": {"type": "string"},
                        "listing_url": {"type": "string"},
                        "text": {"type": "string"},
                    },
                    "required": ["external_key", "listing_url", "text"],
                },
            }
        },
        "required": ["messages"],
    }
    task = await client.create_task(
        task=(
            "Ouvre la messagerie Leboncoin et retourne uniquement les nouveaux "
            "messages recus avec leur identifiant stable et l'URL de l'annonce. "
            "Ne reponds a aucun message."
        ),
        metadata={"template": "inbox_sync"},
        allowed_domains=("leboncoin.fr", "www.leboncoin.fr"),
        session_settings={"profileId": profile_id, "proxyCountryCode": "FR"},
        structured_output=schema,
    )
    detail = await _wait_for_task(client, task)
    parsed = detail.get("structuredOutput") or detail.get("parsedOutput")
    if isinstance(parsed, str):
        import json

        parsed = json.loads(parsed)
    return parsed.get("messages", []) if isinstance(parsed, dict) else []


async def _persist_inbound_message(
    account_id: uuid.UUID, message: dict
) -> tuple[bool, list[str]]:
    text = str(message.get("text", ""))
    external_key = f"inbound:{str(message.get('external_key', ''))[:130]}"
    listing_url = str(message.get("listing_url", ""))
    phones = extract_phone_numbers(text)
    async with get_db() as db:
        listing = await db.scalar(select(Listing).where(Listing.url == listing_url))
        result = await db.execute(
            pg_insert(LbcMessageLog)
            .values(
                external_key=external_key,
                listing_id=listing.id if listing else None,
                account_id=account_id,
                direction=LbcMessageDirection.INBOUND,
                status=LbcMessageStatus.RECEIVED,
                content_hash=hashlib.sha256(text.encode()).hexdigest(),
                preview=text[:160],
                phone_extracted=bool(phones),
                processed_at=datetime.now(UTC),
            )
            .on_conflict_do_nothing(index_elements=["external_key"])
            .returning(LbcMessageLog.id)
        )
        inserted = result.scalar_one_or_none() is not None
        if inserted and phones and listing is not None:
            listing.phone = phones[0]
    return inserted, phones


async def _send_message_task(
    client: BrowserUseCloudClient, profile_id: str, listing_url: str, message: str
) -> dict:
    task = await client.create_task(
        task=(
            "Ouvre l'annonce cible, ouvre la messagerie vendeur, envoie exactement "
            f"le message suivant puis confirme l'envoi: {message}\nURL: {listing_url}"
        ),
        metadata={"template": "messaging_send"},
        allowed_domains=("leboncoin.fr", "www.leboncoin.fr"),
        session_settings={"profileId": profile_id, "proxyCountryCode": "FR"},
    )
    return await _wait_for_task(client, task)


async def _wait_for_task(client: BrowserUseCloudClient, task: dict) -> dict:
    task_id = task.get("id") or task.get("taskId")
    settings = get_settings()
    elapsed = 0
    while elapsed < settings.browser_use_task_timeout_seconds:
        status = await client.get_task_status(task_id)
        if status.get("status") in {"finished", "stopped"}:
            return await client.get_task(task_id)
        await asyncio.sleep(settings.browser_use_poll_interval_seconds)
        elapsed += settings.browser_use_poll_interval_seconds
    await client.stop_task(task_id)
    raise TimeoutError("Browser Use messaging task timed out")


async def _queue_message(
    external_key: str,
    listing_id: uuid.UUID,
    account_id: uuid.UUID,
    message: str,
) -> bool:
    async with get_db() as db:
        result = await db.execute(
            pg_insert(LbcMessageLog)
            .values(
                external_key=external_key,
                listing_id=listing_id,
                account_id=account_id,
                direction=LbcMessageDirection.OUTBOUND,
                status=LbcMessageStatus.QUEUED,
                content_hash=hashlib.sha256(message.encode()).hexdigest(),
                preview=message[:160],
            )
            .on_conflict_do_nothing(index_elements=["external_key"])
            .returning(LbcMessageLog.id)
        )
        return result.scalar_one_or_none() is not None


async def _mark_message(
    external_key: str, status: LbcMessageStatus, error_code: str | None = None
) -> None:
    async with get_db() as db:
        await db.execute(
            update(LbcMessageLog)
            .where(LbcMessageLog.external_key == external_key)
            .values(
                status=status,
                error_code=error_code,
                processed_at=datetime.now(UTC),
            )
        )


async def _today_account_usage() -> dict[uuid.UUID, int]:
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    async with get_db() as db:
        rows = await db.execute(
            select(LbcMessageLog.account_id, func.count())
            .where(
                LbcMessageLog.direction == LbcMessageDirection.OUTBOUND,
                LbcMessageLog.status == LbcMessageStatus.SENT,
                LbcMessageLog.created_at >= start,
            )
            .group_by(LbcMessageLog.account_id)
        )
    return {account_id: count for account_id, count in rows if account_id is not None}


async def _may_continue(campaign_id: uuid.UUID, workflow_id: uuid.UUID) -> bool:
    async with get_db() as db:
        campaign = await db.get(Campaign, campaign_id)
        workflow = await db.get(WorkflowRun, workflow_id)
    return bool(
        campaign and workflow
        and campaign.status == CampaignStatus.RUNNING
        and workflow.status == WorkflowStatus.RUNNING
    )


async def _pause_for_quota(campaign_id: uuid.UUID, workflow_id: uuid.UUID) -> None:
    async with get_db() as db:
        await db.execute(
            update(Campaign).where(Campaign.id == campaign_id).values(
                status=CampaignStatus.PAUSED,
                last_error="All LBC account quotas are exhausted",
            )
        )
        await db.execute(
            update(WorkflowRun).where(WorkflowRun.id == workflow_id).values(
                status=WorkflowStatus.PAUSED,
                last_error="All LBC account quotas are exhausted",
            )
        )


async def _finish_failed(
    campaign_id: uuid.UUID, workflow_id: uuid.UUID, error: str
) -> None:
    async with get_db() as db:
        await db.execute(
            update(Campaign).where(Campaign.id == campaign_id).values(
                status=CampaignStatus.PAUSED, last_error=error
            )
        )
        await db.execute(
            update(WorkflowRun).where(WorkflowRun.id == workflow_id).values(
                status=WorkflowStatus.FAILED,
                last_error=error,
                finished_at=datetime.now(UTC),
            )
        )
