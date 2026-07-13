"""Persist inbound calls and correlate their most recent listing."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import get_db
from app.services.sms_inbox import normalize_inbound_phone
from app.tables import CallLog, Contact, Listing


async def record_incoming_call(sim_id: str, sender: str, external_key: str) -> None:
    phone = normalize_inbound_phone(sender)
    if not phone:
        return
    async with get_db() as db:
        contact = (
            await db.execute(select(Contact).where(Contact.phone_e164 == phone))
        ).scalar_one_or_none()
        listing = (
            await db.execute(
                select(Listing)
                .where(
                    (Listing.phone == phone)
                    | (Listing.contact_id == (contact.id if contact else None))
                )
                .order_by(Listing.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        await db.execute(
            pg_insert(CallLog)
            .values(
                phone_e164=phone,
                sim_id=sim_id,
                contact_id=contact.id if contact else None,
                listing_id=listing.id if listing else None,
                external_key=external_key,
            )
            .on_conflict_do_nothing(index_elements=["external_key"])
        )
