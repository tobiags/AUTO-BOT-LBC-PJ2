"""
Envoi d'une campagne SMS (Workflow WF-02).
"""
import asyncio
import logging
import random
import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import sentry_sdk
from sqlalchemy import func, select, update

from app import boundaries
from app.config import get_settings
from app.db import get_db
from app.models import CampaignStatus, ListingStatus, SmsStatus, WorkflowStatus
from app.services.blacklist import is_blacklisted
from app.tables import Campaign, Listing, SmsLog, WorkflowRun

log = logging.getLogger(__name__)
settings = get_settings()
PARIS_TZ = ZoneInfo("Europe/Paris")
STOP_NOTICE = "STOP au {stop_number} pour ne plus recevoir de SMS"
CAMPAIGN_BATCH_SIZE = 200


def is_within_sms_window() -> bool:
    now_paris = datetime.now(PARIS_TZ)
    return settings.sms_hour_start <= now_paris.hour < settings.sms_hour_end


def next_sms_window_start(now: datetime | None = None) -> datetime:
    current = now.astimezone(PARIS_TZ) if now else datetime.now(PARIS_TZ)
    opening_today = current.replace(
        hour=settings.sms_hour_start,
        minute=0,
        second=0,
        microsecond=0,
    )
    if current.hour < settings.sms_hour_start:
        return opening_today
    return opening_today + timedelta(days=1)


def render_sms_body(template: str, *, url: str, title: str) -> str:
    body = template.format(url=url, title=title)
    stop_notice = STOP_NOTICE.format(stop_number=settings.sms_stop_number)
    if stop_notice.lower() in body.lower():
        return body
    return f"{body}\n{stop_notice}"


async def _select_best_sim(available_sims: list[dict], daily_quotas: dict[str, int]) -> dict | None:
    eligible = [
        sim
        for sim in available_sims
        if sim.get("status") == "active" and daily_quotas.get(sim["id"], 0) > 0
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda sim: daily_quotas.get(sim["id"], 0))


async def _compute_inter_sms_delay_seconds(sim_id: str, now: datetime | None = None) -> int:
    target_gap_seconds = random.randint(120, 720)

    async with get_db() as db:
        result = await db.execute(
            select(SmsLog.sent_at)
            .where(SmsLog.sim_id == sim_id, SmsLog.status == SmsStatus.SENT)
            .order_by(SmsLog.sent_at.desc())
            .limit(1)
        )
        last_sent_at = result.scalar_one_or_none()

    if last_sent_at is None:
        return target_gap_seconds

    current = now or datetime.now(UTC)
    if last_sent_at.tzinfo is None:
        last_sent_at = last_sent_at.replace(tzinfo=UTC)
    elapsed_seconds = max(0, int((current - last_sent_at).total_seconds()))
    return max(0, target_gap_seconds - elapsed_seconds)


async def run_campaign(campaign_id: str, workflow_id: str | None = None) -> dict:
    if not is_within_sms_window():
        scheduled_for = next_sms_window_start()
        async with get_db() as db:
            await db.execute(
                update(Campaign)
                .where(Campaign.id == uuid.UUID(campaign_id))
                .values(scheduled_at=scheduled_for, last_error=None)
            )
        log.info(
            "Campagne %s - hors fenetre horaire R01, replanifiee pour %s.",
            campaign_id,
            scheduled_for.isoformat(),
        )
        return {
            "status": "deferred",
            "sent": 0,
            "failed": 0,
            "scheduled_for": scheduled_for.isoformat(),
        }

    campaign_uuid = uuid.UUID(campaign_id)
    workflow_uuid = uuid.UUID(workflow_id) if workflow_id else None

    async with get_db() as db:
        campaign = await db.get(Campaign, campaign_uuid)
        if not campaign:
            raise ValueError(f"Campagne introuvable : {campaign_id}")
        if campaign.status not in (CampaignStatus.PENDING, CampaignStatus.RUNNING):
            return {"status": campaign.status, "sent": campaign.sent, "failed": campaign.failed}

        campaign.status = CampaignStatus.RUNNING
        campaign.scheduled_at = None
        campaign.last_error = None
        previous_sent = campaign.sent or 0
        previous_failed = campaign.failed or 0
        await db.flush()

        assigned_count_result = await db.execute(
            select(func.count()).select_from(Listing).where(Listing.campaign_id == campaign_uuid)
        )
        has_assigned = (assigned_count_result.scalar() or 0) > 0

        listing_q = select(Listing).where(
            Listing.phone.isnot(None),
            Listing.status == ListingStatus.NOUVELLE,
        )
        if has_assigned:
            listing_q = listing_q.where(Listing.campaign_id == campaign_uuid)

        result = await db.execute(listing_q.limit(CAMPAIGN_BATCH_SIZE + 1))
        fetched_listings = result.scalars().all()
        has_more_backlog = len(fetched_listings) > CAMPAIGN_BATCH_SIZE
        listings = fetched_listings[:CAMPAIGN_BATCH_SIZE]
        if workflow_uuid is not None:
            workflow = await db.get(WorkflowRun, workflow_uuid)
            if workflow is not None:
                workflow.status = WorkflowStatus.RUNNING
                workflow.started_at = workflow.started_at or datetime.now(UTC)
                workflow.progress_total = await db.scalar(
                    select(func.count()).select_from(Listing).where(
                        Listing.phone.isnot(None),
                        Listing.status == ListingStatus.NOUVELLE,
                    )
                )

    sent = 0
    failed = 0
    paused_for_quota = False
    failed_for_credit = False
    interrupted_status: CampaignStatus | None = None
    last_error: str | None = None
    sims = await boundaries.get_sim_list()
    daily_quotas: dict[str, int] = {sim["id"]: sim.get("quota_remaining", 15) for sim in sims}

    for listing in listings:
        if workflow_uuid is not None:
            interrupted_status = await _interrupted_campaign_status(
                campaign_uuid, workflow_uuid
            )
            if interrupted_status is not None:
                break
        if await is_blacklisted(listing.phone):
            log.debug("Skipping blacklisted phone %s", listing.phone)
            continue

        sim = await _select_best_sim(sims, daily_quotas)
        if sim is None:
            paused_for_quota = True
            log.warning("Plus de quota SIM disponible - campagne suspendue.")
            break

        delay = await _compute_inter_sms_delay_seconds(sim["id"])
        await asyncio.sleep(delay)

        message = render_sms_body(
            campaign.message_template,
            url=listing.url,
            title=listing.title or "",
        )

        try:
            result = await boundaries.send_sms(sim["id"], listing.phone, message)
            if result.status == SmsStatus.SENT:
                sent += 1
                daily_quotas[sim["id"]] -= 1
                async with get_db() as db:
                    db.add(
                        SmsLog(
                            sim_id=sim["id"],
                            to_phone=listing.phone,
                            listing_id=listing.id,
                            body=message,
                            status=SmsStatus.SENT,
                            project="P2",
                            cost_eur=result.cost,
                            campaign_id=campaign_uuid,
                        )
                    )
                    await db.execute(
                        update(Listing)
                        .where(Listing.id == listing.id)
                        .values(status=ListingStatus.SMS_ENVOYE)
                    )
            else:
                failed += 1
        except boundaries.InsufficientCreditError as exc:
            failed += 1
            failed_for_credit = True
            last_error = str(exc)
            sentry_sdk.capture_exception(exc)
            log.error("Campagne %s stoppee - credit SMSTools insuffisant: %s", campaign_id, exc)
            break
        except Exception as exc:
            log.error("Echec envoi SMS vers %s : %s", listing.phone, exc)
            failed += 1
            last_error = str(exc)

    if interrupted_status is not None:
        final_status = interrupted_status
        result_status = interrupted_status.value.lower()
    elif failed_for_credit:
        final_status = CampaignStatus.FAILED
        result_status = "failed"
    elif paused_for_quota:
        final_status = CampaignStatus.PAUSED
        result_status = "paused"
    elif has_more_backlog:
        final_status = CampaignStatus.RUNNING
        result_status = "running"
    else:
        final_status = CampaignStatus.COMPLETED
        result_status = "completed"

    async with get_db() as db:
        await db.execute(
            update(Campaign)
            .where(Campaign.id == campaign_uuid)
            .values(
                status=final_status,
                sent=previous_sent + sent,
                failed=previous_failed + failed,
                scheduled_at=None,
                last_error=last_error,
            )
        )
        if workflow_uuid is not None:
            workflow = await db.get(WorkflowRun, workflow_uuid)
            if workflow is not None:
                workflow.progress_current += sent + failed
                workflow.batch_number += 1
                workflow.checkpoint = {
                    "campaign_id": campaign_id,
                    "last_batch_sent": sent,
                    "last_batch_failed": failed,
                    "has_more_backlog": has_more_backlog,
                }
                workflow.status = _campaign_to_workflow_status(final_status)
                if workflow.status in {
                    WorkflowStatus.COMPLETED,
                    WorkflowStatus.FAILED,
                    WorkflowStatus.CANCELLED,
                }:
                    workflow.finished_at = datetime.now(UTC)

    log.info(
        "Campagne %s terminee - status=%s sent=%d failed=%d",
        campaign_id,
        result_status,
        sent,
        failed,
    )
    return {"status": result_status, "sent": sent, "failed": failed}


async def _interrupted_campaign_status(
    campaign_id: uuid.UUID, workflow_id: uuid.UUID
) -> CampaignStatus | None:
    async with get_db() as db:
        campaign = await db.get(Campaign, campaign_id)
        workflow = await db.get(WorkflowRun, workflow_id)
    if campaign is None or workflow is None:
        return CampaignStatus.CANCELLED
    if campaign.status in {CampaignStatus.PAUSED, CampaignStatus.CANCELLED}:
        return campaign.status
    if workflow.status in {WorkflowStatus.PAUSED, WorkflowStatus.CANCELLED}:
        return (
            CampaignStatus.PAUSED
            if workflow.status == WorkflowStatus.PAUSED
            else CampaignStatus.CANCELLED
        )
    return None


def _campaign_to_workflow_status(status: CampaignStatus) -> WorkflowStatus:
    return {
        CampaignStatus.PENDING: WorkflowStatus.PENDING,
        CampaignStatus.RUNNING: WorkflowStatus.RUNNING,
        CampaignStatus.PAUSED: WorkflowStatus.PAUSED,
        CampaignStatus.COMPLETED: WorkflowStatus.COMPLETED,
        CampaignStatus.FAILED: WorkflowStatus.FAILED,
        CampaignStatus.CANCELLED: WorkflowStatus.CANCELLED,
    }[status]
