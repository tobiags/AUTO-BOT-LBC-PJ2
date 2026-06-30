"""
Envoi d'une campagne SMS (Workflow WF-02).
"""
import asyncio
import logging
import random
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update

from app import boundaries
from app.config import get_settings
from app.db import get_db
from app.models import CampaignStatus, ListingStatus, SmsStatus
from app.services.blacklist import is_blacklisted
from app.tables import Campaign, Listing, SmsLog

log = logging.getLogger(__name__)
settings = get_settings()
PARIS_TZ = ZoneInfo("Europe/Paris")


def is_within_sms_window() -> bool:
    now_paris = datetime.now(PARIS_TZ)
    return settings.sms_hour_start <= now_paris.hour < settings.sms_hour_end


async def _select_best_sim(available_sims: list[dict], daily_quotas: dict[str, int]) -> dict | None:
    eligible = [
        sim
        for sim in available_sims
        if sim.get("status") == "active" and daily_quotas.get(sim["id"], 0) > 0
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda sim: daily_quotas.get(sim["id"], 0))


async def run_campaign(campaign_id: str) -> dict:
    if not is_within_sms_window():
        log.info("Campagne %s - hors fenetre horaire R01, mise en attente.", campaign_id)
        return {"status": "deferred", "sent": 0, "failed": 0}

    campaign_uuid = uuid.UUID(campaign_id)

    async with get_db() as db:
        campaign = await db.get(Campaign, campaign_uuid)
        if not campaign:
            raise ValueError(f"Campagne introuvable : {campaign_id}")
        if campaign.status not in (CampaignStatus.PENDING, CampaignStatus.RUNNING):
            return {"status": campaign.status, "sent": campaign.sent, "failed": campaign.failed}

        campaign.status = CampaignStatus.RUNNING
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

        result = await db.execute(listing_q.limit(200))
        listings = result.scalars().all()

    sent = 0
    failed = 0
    paused_for_quota = False
    sims = await boundaries.get_sim_list()
    daily_quotas: dict[str, int] = {sim["id"]: sim.get("quota_remaining", 15) for sim in sims}

    for listing in listings:
        if await is_blacklisted(listing.phone):
            log.debug("Skipping blacklisted phone %s", listing.phone)
            continue

        sim = await _select_best_sim(sims, daily_quotas)
        if sim is None:
            paused_for_quota = True
            log.warning("Plus de quota SIM disponible - campagne suspendue.")
            break

        delay = random.uniform(120, 720)
        await asyncio.sleep(delay)

        message = campaign.message_template.format(url=listing.url, title=listing.title or "")

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
        except Exception as exc:
            log.error("Echec envoi SMS vers %s : %s", listing.phone, exc)
            failed += 1

    final_status = CampaignStatus.PAUSED if paused_for_quota else CampaignStatus.COMPLETED
    result_status = "paused" if paused_for_quota else "completed"

    async with get_db() as db:
        await db.execute(
            update(Campaign)
            .where(Campaign.id == campaign_uuid)
            .values(status=final_status, sent=sent, failed=failed)
        )

    log.info("Campagne %s terminee - status=%s sent=%d failed=%d", campaign_id, result_status, sent, failed)
    return {"status": result_status, "sent": sent, "failed": failed}
