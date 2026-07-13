"""Contact lookup used by the incoming-call dashboard search bar."""

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import select

from app.db import get_db
from app.models import CallOutcomeUpdate, ContactLookupOut
from app.services.sms_inbox import normalize_inbound_phone
from app.tables import CallLog, Contact, Listing

router = APIRouter(prefix="/api/v1/contacts", tags=["contacts"])


@router.get("/lookup", response_model=ContactLookupOut)
async def lookup_contact(
    phone: str = Query(min_length=6, max_length=30),
    x_operator_role: Annotated[str, Header()] = "operateur",
):
    normalized = normalize_inbound_phone(phone)
    if not normalized:
        raise HTTPException(422, detail={"code": "INVALID_PHONE"})
    async with get_db() as db:
        contact = (
            await db.execute(select(Contact).where(Contact.phone_e164 == normalized))
        ).scalar_one_or_none()
        listings = (
            await db.scalars(
                select(Listing)
                .where(
                    (Listing.phone == normalized)
                    | (Listing.contact_id == (contact.id if contact else None))
                )
                .order_by(Listing.created_at.desc())
            )
        ).all()
        calls = (
            await db.scalars(
                select(CallLog)
                .where(CallLog.phone_e164 == normalized)
                .order_by(CallLog.called_at.desc())
            )
        ).all()
    return ContactLookupOut(
        phone_e164=normalized,
        contact_id=contact.id if contact else None,
        listings=[
            {
                "id": str(item.id),
                "url": item.url,
                "title": item.title,
                "price": item.price,
                "make": item.make,
                "model": item.model,
                "source": item.source,
                "created_at": item.created_at,
            }
            for item in listings
        ],
        calls=[
            {
                "id": str(item.id),
                "called_at": item.called_at,
                "result": item.result,
                "notes": item.notes,
                "listing_id": str(item.listing_id) if item.listing_id else None,
            }
            for item in calls
        ],
    )


@router.patch("/calls/{call_id}")
async def update_call_outcome(call_id: str, payload: CallOutcomeUpdate):
    async with get_db() as db:
        call = await db.get(CallLog, call_id)
        if call is None:
            raise HTTPException(404, detail={"code": "CALL_NOT_FOUND"})
        call.result = payload.result
        call.notes = payload.notes
        return {"ok": True, "call_id": call_id}
