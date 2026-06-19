"""
Webhook appel entrant → POST /webhooks/call (WF-03).
Push WebSocket vers le back-office avec le contexte de l'annonce.
Règle R12 : idempotent.
"""
import hashlib
import logging

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import get_db
from app.models import CallWebhookPayload, IncomingCallEvent
from app.tables import Listing, SmsLog, WebhookEvent
from app.ws import ws_manager

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = logging.getLogger(__name__)


@router.post("/call")
async def receive_call(payload: CallWebhookPayload):
    event_key = hashlib.sha256(
        f"call:{payload.from_}:{payload.sim_id}:{payload.timestamp}".encode()
    ).hexdigest()[:32]

    async with get_db() as db:
        result = await db.execute(
            pg_insert(WebhookEvent)
            .values(event_key=event_key, source="call", processed=False)
            .on_conflict_do_nothing(index_elements=["event_key"])
            .returning(WebhookEvent.id)
        )
        if result.scalar() is None:
            return {"ok": True, "duplicate": True}

    # Lookup annonce associée — dernier SMS envoyé depuis cette SIM vers ce numéro
    listing_data = None
    async with get_db() as db:
        await db.execute(
            select(SmsLog.campaign_id)
            .where(SmsLog.sim_id == payload.sim_id, SmsLog.to_phone == payload.from_)
            .order_by(SmsLog.sent_at.desc())
            .limit(1)
        )
        # Simplified: look up listing directly by phone
        listing_result = await db.execute(
            select(Listing)
            .where(Listing.phone == payload.from_)
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

    event = IncomingCallEvent(caller=payload.from_, listing=listing_data)
    await ws_manager.broadcast(event.model_dump())
    log.info("Appel entrant %s — push WS (listing=%s)", payload.from_, bool(listing_data))

    return {"ok": True}
