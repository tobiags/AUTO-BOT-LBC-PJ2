"""
Envoi d'une campagne SMS (Workflow WF-02).

Règle R01 : fenêtre horaire 08h–20h (heure Paris).
Règle R02 : filtrage blacklist cross-projets avant envoi.
Règle R05 : délai aléatoire 2–12 min entre messages, quotas progressifs.
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
    """R01 — vérifie si l'heure courante (Paris) est dans la fenêtre autorisée."""
    now_paris = datetime.now(PARIS_TZ)
    return settings.sms_hour_start <= now_paris.hour < settings.sms_hour_end


async def _select_best_sim(available_sims: list[dict], daily_quotas: dict[str, int]) -> dict | None:
    """
    Round-robin pondéré : SIM ACTIVE avec le plus de quota restant.
    Exclut les SIMs RALENTIE / BLOQUÉE.
    """
    eligible = [
        s for s in available_sims
        if s.get("status") == "active" and daily_quotas.get(s["id"], 0) > 0
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda s: daily_quotas.get(s["id"], 0))


async def run_campaign(campaign_id: str) -> dict:
    """
    Exécute une campagne SMS. Retourne les statistiques d'envoi.
    Appelé par Celery task run_campaign_task.
    """
    if not is_within_sms_window():
        log.info("Campagne %s — hors fenêtre horaire R01, mise en attente.", campaign_id)
        return {"status": "deferred", "sent": 0, "failed": 0}

    campaign_uuid = uuid.UUID(campaign_id)

    # Charger la campagne
    async with get_db() as db:
        campaign = await db.get(Campaign, campaign_uuid)
        if not campaign:
            raise ValueError(f"Campagne introuvable : {campaign_id}")
        if campaign.status not in (CampaignStatus.PENDING, CampaignStatus.RUNNING):
            return {"status": campaign.status, "sent": campaign.sent, "failed": campaign.failed}

        # Passage en RUNNING
        campaign.status = CampaignStatus.RUNNING
        await db.flush()

        # Annonces NOUVELLES avec numéro de téléphone — filtrées blacklist (R02)
        # Si des annonces sont pré-assignées (POST /campaigns/{id}/listings), les cibler.
        assigned_count_result = await db.execute(
            select(func.count())
            .select_from(Listing)
            .where(Listing.campaign_id == campaign_uuid)
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
    sims = await boundaries.get_sim_list()
    daily_quotas: dict[str, int] = {s["id"]: s.get("quota_remaining", 15) for s in sims}

    for listing in listings:
        # R02 — vérification blacklist
        if await is_blacklisted(listing.phone):
            log.debug("Skipping blacklisted phone %s", listing.phone)
            continue

        sim = await _select_best_sim(sims, daily_quotas)
        if sim is None:
            log.warning("Plus de quota SIM disponible — campagne suspendue.")
            break

        # R05 — délai aléatoire 2–12 min entre messages (anti-pattern milliseconde)
        delay = random.uniform(120, 720)
        await asyncio.sleep(delay)

        message = campaign.message_template.format(
            url=listing.url,
            title=listing.title or "",
        )

        try:
            result = await boundaries.send_sms(sim["id"], listing.phone, message)
            if result.status == SmsStatus.SENT:
                sent += 1
                daily_quotas[sim["id"]] -= 1
                async with get_db() as db:
                    db.add(SmsLog(
                        sim_id=sim["id"],
                        to_phone=listing.phone,
                        body=message,
                        status=SmsStatus.SENT,
                        project="P2",
                        cost_eur=result.cost,
                        campaign_id=campaign_uuid,
                    ))
                    await db.execute(
                        update(Listing)
                        .where(Listing.id == listing.id)
                        .values(status=ListingStatus.SMS_ENVOYE)
                    )
            else:
                failed += 1
        except Exception as exc:
            log.error("Échec envoi SMS vers %s : %s", listing.phone, exc)
            failed += 1

    async with get_db() as db:
        await db.execute(
            update(Campaign)
            .where(Campaign.id == campaign_uuid)
            .values(status=CampaignStatus.COMPLETED, sent=sent, failed=failed)
        )

    log.info("Campagne %s terminée — sent=%d failed=%d", campaign_id, sent, failed)
    return {"status": "completed", "sent": sent, "failed": failed}
