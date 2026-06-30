"""
Webhook SMSTools -> POST /webhooks/call (CALL_FORWARDING).
Push WebSocket vers le back-office.
"""
import logging

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import get_db
from app.models import CallToolsWebhookItem, IncomingCallEvent
from app.tables import Listing, SmsLog, WebhookEvent
from app.ws import ws_manager

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = logging.getLogger(__name__)


def _listing_payload(listing: Listing) -> dict:
    vehicle = " ".join(part for part in [listing.make, listing.model] if part).strip() or None
    return {
        "url": listing.url,
        "title": listing.title,
        "price": listing.price,
        "km": listing.km,
        "source": listing.source,
        "vehicle": vehicle,
        "make": listing.make,
        "model": listing.model,
    }


async def _find_listing_for_call(sim_id: str, from_number: str) -> dict | None:
    async with get_db() as db:
        sms_result = await db.execute(
            select(SmsLog)
            .where(SmsLog.sim_id == sim_id, SmsLog.to_phone == from_number)
            .order_by(SmsLog.sent_at.desc())
            .limit(1)
        )
        sms_log = sms_result.scalar_one_or_none()
        if sms_log and sms_log.listing_id:
            listing_result = await db.execute(
                select(Listing).where(Listing.id == sms_log.listing_id).limit(1)
            )
            listing = listing_result.scalar_one_or_none()
            if listing:
                return _listing_payload(listing)

        listing_result = await db.execute(
            select(Listing)
            .where(Listing.phone == from_number)
            .order_by(Listing.created_at.desc())
            .limit(1)
        )
        listing = listing_result.scalar_one_or_none()
        if listing:
            return _listing_payload(listing)

    return None


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

    listing_data = await _find_listing_for_call(sim_id, from_number)
    if not listing_data:
        log.info(
            "Appel entrant %s (SIM %s) - aucun listing corrélé, pas de push WS",
            from_number,
            sim_id,
        )
        return {"ok": True, "matched": False}

    event = IncomingCallEvent(caller=from_number, listing=listing_data)
    await ws_manager.broadcast(event.model_dump())
    log.info(
        "Appel entrant %s (SIM %s) - push WS (listing=%s)",
        from_number,
        sim_id,
        bool(listing_data),
    )

    return {"ok": True}
