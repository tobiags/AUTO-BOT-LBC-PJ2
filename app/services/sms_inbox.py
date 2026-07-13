"""Persist and classify inbound SMS before applying sequence controls."""

from datetime import UTC, datetime

import phonenumbers
from sqlalchemy import select

from app.db import get_db
from app.models import ContactStatus, SmsClassification, SmsDirection, SmsStatus
from app.services.sms_sequence import stop_contact_sequences
from app.tables import Contact, Listing, SmsLog, WebhookEvent


def normalize_inbound_phone(raw: str) -> str | None:
    try:
        parsed = phonenumbers.parse(raw, "FR")
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(parsed):
        return None
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def classify_sms(body: str) -> SmsClassification:
    normalized = " ".join(body.lower().strip().split())
    if normalized in {"stop", "arret", "arrêt", "desabonnement", "désabonnement"}:
        return SmsClassification.STOP
    if any(
        word in normalized
        for word in ("intéressé", "interesse", "disponible", "appelez", "appellez", "oui")
    ):
        return SmsClassification.POSITIVE
    if any(word in normalized for word in ("pas intéressé", "pas interesse", "vendu", "non merci")):
        return SmsClassification.NEGATIVE
    if any(
        word in normalized
        for word in ("combien", "prix", "kilométrage", "kilometrage", "où", "ou ")
    ):
        return SmsClassification.INFORMATION
    if normalized:
        return SmsClassification.AMBIGUOUS
    return SmsClassification.INVALID


async def record_inbound_sms(sim_id: str, sender: str, body: str, event_key: str) -> dict:
    phone = normalize_inbound_phone(sender)
    classification = SmsClassification.INVALID if phone is None else classify_sms(body)
    if phone is None:
        async with get_db() as db:
            db.add(
                SmsLog(
                    sim_id=sim_id,
                    to_phone=sender[:30],
                    body=body,
                    status=SmsStatus.RECEIVED,
                    direction=SmsDirection.INBOUND.value,
                    classification=classification.value,
                    idempotency_key=f"inbound:{event_key}",
                    received_at=datetime.now(UTC),
                )
            )
        return {"status": "invalid", "classification": classification.value}
    async with get_db() as db:
        contact = (
            await db.execute(select(Contact).where(Contact.phone_e164 == phone))
        ).scalar_one_or_none()
        if contact is None:
            contact = Contact(phone_e164=phone)
            db.add(contact)
            await db.flush()
        listing = (
            await db.execute(
                select(Listing)
                .where(Listing.contact_id == contact.id)
                .order_by(Listing.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        db.add(
            SmsLog(
                sim_id=sim_id,
                to_phone=phone,
                body=body,
                status=SmsStatus.RECEIVED,
                direction=SmsDirection.INBOUND.value,
                contact_id=contact.id,
                listing_id=listing.id if listing else None,
                campaign_id=listing.campaign_id if listing else None,
                classification=classification.value,
                idempotency_key=f"inbound:{event_key}",
                received_at=datetime.now(UTC),
            )
        )
        contact.last_classification = classification.value
        contact.last_inbound_at = datetime.now(UTC)
        if classification == SmsClassification.STOP:
            contact.status = ContactStatus.DO_NOT_CONTACT.value
        elif classification == SmsClassification.INVALID:
            contact.status = ContactStatus.INVALID.value
        else:
            contact.status = ContactStatus.PAUSED.value
        contact_id = contact.id
    if classification in {
        SmsClassification.STOP,
        SmsClassification.POSITIVE,
        SmsClassification.NEGATIVE,
        SmsClassification.INFORMATION,
        SmsClassification.INVALID,
        SmsClassification.AMBIGUOUS,
    }:
        await stop_contact_sequences(
            contact_id,
            ContactStatus.DO_NOT_CONTACT
            if classification == SmsClassification.STOP
            else ContactStatus.PAUSED,
        )
    return {
        "status": "recorded",
        "phone": phone,
        "classification": classification.value,
        "listing_id": str(listing.id) if listing else None,
    }


async def replay_pending_sms_events(limit: int = 100) -> int:
    processed = 0
    async with get_db() as db:
        events = (
            await db.scalars(
                select(WebhookEvent)
                .where(WebhookEvent.source == "sms", WebhookEvent.processed.is_(False))
                .order_by(WebhookEvent.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
        for event in events:
            payload = event.payload or {}
            if isinstance(payload, list) and payload:
                message = payload[0].get("message", {})
                sim_id = str(message.get("receiver", ""))
                sender = str(message.get("sender", ""))
                body = str(message.get("content", ""))
            else:
                sim_id = str(payload.get("sim_id") or payload.get("to") or "")
                sender = str(payload.get("from") or payload.get("sender") or "")
                body = str(payload.get("body") or payload.get("content") or "")
            try:
                await record_inbound_sms(sim_id, sender, body, event.event_key)
                event.processed = True
                processed += 1
            except Exception:
                continue
    return processed
