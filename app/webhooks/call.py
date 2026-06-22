"""
Webhook SMSTools → POST /webhooks/call  (CALL_FORWARDING).
Push WebSocket vers le back-office. Règle R12 : idempotent via webhook_id.
"""
import logging

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import get_db
from app.models import CallToolsWebhookItem, IncomingCallEvent
from app.tables import Listing, WebhookEvent
from app.ws import ws_manager

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = logging.getLogger(__name__)


@router.post("/call")
async def receive_call(payload: list[CallToolsWebhookItem]):
    if not payload:
        return {"ok": True}

    item = payload[0]
    event_key = item.webhook_id[:32]
    from_number = item.message.sender
    sim_id = item.message.receiver

    async with get_db() as db:
        result = await db.execute(
            pg_insert(WebhookEvent)
            .values(event_key=event_key, source="call", processed=False)
            .on_conflict_do_nothing(index_elements=["event_key"])
            .returning(WebhookEvent.id)
        )
        if result.scalar() is None:
            return {"ok": True, "duplicate": True}

    # Lookup annonce associée au numéro appelant
    listing_data = None
    async with get_db() as db:
        listing_result = await db.execute(
            select(Listing)
            .where(Listing.phone == from_number)
            .order_by(Listing.created_at.desc())
            .limit(1)
        )
        listing = listing_result.scalar_one_or_none()
        if listing:
            listing_data = {
                "url": listing.url,
                "title": listing.title,
                "price": listing.price,
                "km": listing.km,
                "source": listing.source,
            }

    event = IncomingCallEvent(caller=from_number, listing=listing_data)
    await ws_manager.broadcast(event.model_dump())
    log.info("Appel entrant %s (SIM %s) — push WS (listing=%s)", from_number, sim_id, bool(listing_data))

    return {"ok": True}
