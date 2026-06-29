"""
Webhook SMSTools -> POST /webhooks/sms (INBOX_MESSAGE).
Gere STOP (WF-05). Regle R12 : idempotent via webhook_id.
"""
import hashlib
import logging
from typing import Any

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


def _event_key(sim_id: str, from_number: str, body: str, timestamp: str) -> str:
    raw = f"{sim_id}:{from_number}:{body}:{timestamp}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _extract_sms_payload(
    payload: list[SmsToolsWebhookItem] | dict[str, Any],
) -> tuple[str, str, str, str]:
    if isinstance(payload, list):
        if not payload:
            return "", "", "", ""

        item = payload[0]
        return (
            item.message.receiver,
            item.message.sender,
            item.message.content,
            item.webhook_id[:32],
        )

    sim_id = str(payload.get("sim_id") or payload.get("to") or "")
    from_number = str(payload.get("from") or payload.get("sender") or "")
    body = str(payload.get("body") or payload.get("content") or "")
    timestamp = str(payload.get("ts") or payload.get("timestamp") or "")
    return sim_id, from_number, body, _event_key(sim_id, from_number, body, timestamp)


@router.post("/sms")
async def receive_sms(
    payload: list[SmsToolsWebhookItem] | dict[str, Any],
    bg: BackgroundTasks,
):
    sim_id, from_number, body, event_key = _extract_sms_payload(payload)
    if not event_key:
        return {"ok": True}

    async with get_db() as db:
        result = await db.execute(
            pg_insert(WebhookEvent)
            .values(event_key=event_key, source="sms", processed=False)
            .on_conflict_do_nothing(index_elements=["event_key"])
            .returning(WebhookEvent.id)
        )
        if result.scalar() is None:
            log.debug("SMS deja traite - event_key=%s", event_key)
            return {"ok": True, "duplicate": True}

    if _is_stop(body):
        log.info("STOP recu de %s (SIM %s) - blacklist", from_number, sim_id)
        await add_to_blacklist(
            phone=from_number,
            source_sim=sim_id,
            source_project="P1+P2",
        )
        bg.add_task(
            boundaries.send_sms,
            sim_id,
            from_number,
            "Vous etes bien desinscrit. Cordialement, AutoTransfert.",
        )
    else:
        log.info("SMS entrant de %s (SIM %s) : %s", from_number, sim_id, body[:80])

    return {"ok": True}
