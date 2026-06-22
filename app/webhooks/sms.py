"""
Webhook SMSTools → POST /webhooks/sms  (INBOX_MESSAGE).
Gère STOP (WF-05). Règle R12 : idempotent via webhook_id.
"""
import logging

from fastapi import APIRouter, BackgroundTasks
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app import boundaries
from app.db import get_db
from app.models import SmsToolsWebhookItem
from app.services.blacklist import add_to_blacklist
from app.tables import WebhookEvent

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = logging.getLogger(__name__)

_STOP_KEYWORDS = {"stop", "arret", "arrêt", "desabonnement", "désabonnement"}


def _is_stop(body: str) -> bool:
    return body.strip().lower() in _STOP_KEYWORDS


@router.post("/sms")
async def receive_sms(payload: list[SmsToolsWebhookItem], bg: BackgroundTasks):
    if not payload:
        return {"ok": True}

    item = payload[0]
    event_key = item.webhook_id[:32]
    sim_id = item.message.receiver
    from_number = item.message.sender
    body = item.message.content

    # Idempotence — R12
    async with get_db() as db:
        result = await db.execute(
            pg_insert(WebhookEvent)
            .values(event_key=event_key, source="sms", processed=False)
            .on_conflict_do_nothing(index_elements=["event_key"])
            .returning(WebhookEvent.id)
        )
        if result.scalar() is None:
            log.debug("SMS déjà traité — webhook_id=%s", item.webhook_id)
            return {"ok": True, "duplicate": True}

    if _is_stop(body):
        log.info("STOP reçu de %s (SIM %s) — blacklist", from_number, sim_id)
        await add_to_blacklist(
            phone=from_number,
            source_sim=sim_id,
            source_project="P1+P2",
        )
        bg.add_task(
            boundaries.send_sms,
            sim_id,
            from_number,
            "Vous êtes bien désinscrit. Cordialement, AutoTransfert.",
        )
    else:
        log.info("SMS entrant de %s (SIM %s) : %s", from_number, sim_id, body[:80])

    return {"ok": True}
