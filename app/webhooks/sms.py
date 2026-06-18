"""
Webhook SMSTools → POST /webhooks/sms.
Gère STOP (WF-05) + appels entrants (WF-03).
Règle R12 : idempotent via table webhook_events.
"""
import hashlib
import logging

from fastapi import APIRouter, BackgroundTasks, Request
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app import boundaries
from app.db import get_db
from app.models import SmsWebhookPayload
from app.services.blacklist import add_to_blacklist
from app.tables import WebhookEvent
from app.ws import ws_manager

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = logging.getLogger(__name__)

_STOP_KEYWORDS = {"stop", "arret", "arrêt", "desabonnement", "désabonnement"}


def _is_stop(body: str) -> bool:
    return body.strip().lower() in _STOP_KEYWORDS


def _event_key(payload: SmsWebhookPayload) -> str:
    """Clé unique pour garantir l'idempotence (R12)."""
    raw = f"sms:{payload.from_}:{payload.ts}:{payload.body[:50]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


@router.post("/sms")
async def receive_sms(payload: SmsWebhookPayload, bg: BackgroundTasks):
    event_key = _event_key(payload)

    # Idempotence — R12
    async with get_db() as db:
        result = await db.execute(
            pg_insert(WebhookEvent)
            .values(event_key=event_key, source="sms", processed=False)
            .on_conflict_do_nothing(index_elements=["event_key"])
            .returning(WebhookEvent.id)
        )
        if result.scalar() is None:
            log.debug("SMS déjà traité — event_key=%s", event_key)
            return {"ok": True, "duplicate": True}

    if _is_stop(payload.body):
        log.info("STOP reçu de %s (SIM %s) — blacklist P1+P2", payload.from_, payload.sim_id)
        await add_to_blacklist(
            phone=payload.from_,
            source_sim=payload.sim_id,
            source_project="P1+P2",
        )
        # Confirmation légale (LCEN)
        bg.add_task(
            boundaries.send_sms,
            payload.sim_id,
            payload.from_,
            "Vous êtes bien désinscrit. Cordialement, AutoTransfert.",
        )
    else:
        log.info("SMS entrant (réponse) de %s : %s", payload.from_, payload.body[:80])

    return {"ok": True}
