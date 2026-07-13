"""Contacts and idempotent SMS follow-up sequences."""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update

from app import boundaries
from app.db import get_db
from app.models import ContactStatus, SequenceStatus, SmsDirection, SmsStatus
from app.services.blacklist import is_blacklisted
from app.services.campaign_runner import render_sms_body
from app.services.phone_extractor import extract_phone
from app.tables import (
    Campaign,
    CampaignMessageTemplate,
    Contact,
    Listing,
    SectorSim,
    SmsLog,
    SmsSequence,
)

SEQUENCE_DELAYS_DAYS = (0, 7, 14, 21, 28, 35, 42, 49)
SMS_VARIANTS = {
    0: (
        (
            "initial_a",
            "Bonjour, votre véhicule {title} nous intéresse. Est-il toujours disponible ? {url}",
        ),
        (
            "initial_b",
            "Bonjour, nous sommes intéressés par {title}. Pouvez-vous confirmer sa "
            "disponibilité ? {url}",
        ),
    ),
    1: (
        (
            "j1_a",
            "Bonjour, je reviens vers vous au sujet de {title}. Merci pour votre retour. {url}",
        ),
        (
            "j1_b",
            "Bonjour, petit suivi concernant {title}. Je reste disponible pour échanger. {url}",
        ),
    ),
    2: (
        ("j2_a", "Bonjour, avez-vous pu voir mon message concernant {title} ? {url}"),
        ("j2_b", "Bonjour, je voulais vérifier si {title} est encore disponible. {url}"),
    ),
    3: (
        (
            "j3_a",
            "Dernier rappel rapproché pour {title}. Nous pouvons échanger quand vous "
            "êtes disponible. {url}",
        ),
        ("j3_b", "Bonjour, souhaitez-vous toujours échanger au sujet de {title} ? {url}"),
    ),
    4: (
        ("j7_a", "Bonjour, votre annonce {title} est-elle encore d'actualité ? {url}"),
        (
            "j7_b",
            "Bonjour, je reprends contact concernant {title}. Est-il toujours disponible ? {url}",
        ),
    ),
    5: (
        (
            "j14_a",
            "Je clôture ma demande concernant {title}. Répondez si le véhicule est "
            "toujours disponible. {url}",
        ),
        (
            "j14_b",
            "Dernier message concernant {title}. Répondez si votre annonce est "
            "toujours active. {url}",
        ),
    ),
    6: (
        (
            "j42_a",
            "Bonjour, je reviens vers vous au sujet de {title}. Est-il toujours disponible ? {url}",
        ),
        ("j42_b", "Dernier suivi de la semaine concernant {title}. Merci pour votre retour. {url}"),
    ),
    7: (
        (
            "j49_a",
            "Dernier message concernant {title}. Répondez si le véhicule est toujours "
            "disponible. {url}",
        ),
        (
            "j49_b",
            "Je clôture cette demande concernant {title}. Nous restons joignables si besoin. {url}",
        ),
    ),
}


def choose_sms_variant(step: int, sequence_id: uuid.UUID | str) -> tuple[str, str]:
    variants = SMS_VARIANTS[step]
    # Stable rotation: same sequence/step always renders the same variant.
    digest = hashlib.sha256(f"{sequence_id}:{step}".encode()).digest()
    return variants[digest[0] % len(variants)]


def next_due_at(step: int, created_at: datetime) -> datetime:
    return created_at + timedelta(days=SEQUENCE_DELAYS_DAYS[step])


def _template_due(template: CampaignMessageTemplate, created_at: datetime) -> datetime:
    hour, minute = (int(value) for value in template.send_time.split(":", 1))
    return (created_at + timedelta(days=template.delay_days)).replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )


async def ensure_contact_and_sequence(listing_id: uuid.UUID, phone: str) -> dict:
    normalized = extract_phone(phone) or phone if phone.startswith("+") else extract_phone(phone)
    if not normalized:
        raise ValueError("invalid_phone")
    if await is_blacklisted(normalized):
        return {"status": "blacklisted", "phone": normalized}

    sequence_created = False
    async with get_db() as db:
        listing = await db.get(Listing, listing_id)
        if listing is None:
            raise ValueError("listing_not_found")
        contact = (
            await db.execute(select(Contact).where(Contact.phone_e164 == normalized))
        ).scalar_one_or_none()
        if contact is None:
            contact = Contact(phone_e164=normalized)
            db.add(contact)
            await db.flush()
        elif contact.status != ContactStatus.ACTIVE.value:
            return {"status": contact.status, "phone": normalized, "contact_id": str(contact.id)}
        listing.phone = normalized
        listing.contact_id = contact.id
        sequence = None
        if listing.campaign_id:
            sequence = (
                await db.execute(
                    select(SmsSequence).where(
                        SmsSequence.listing_id == listing.id,
                        SmsSequence.campaign_id == listing.campaign_id,
                    )
                )
            ).scalar_one_or_none()
            if sequence is None:
                created = datetime.now(UTC)
                sequence = SmsSequence(
                    contact_id=contact.id,
                    listing_id=listing.id,
                    campaign_id=listing.campaign_id,
                    current_step=-1,
                    next_due_at=created,
                )
                db.add(sequence)
                sequence_created = True
        result = {
            "status": "scheduled" if sequence else "contacted",
            "phone": normalized,
            "contact_id": str(contact.id),
            "sequence_id": str(sequence.id) if sequence else None,
        }
    if sequence_created:
        from app.tasks import run_sms_sequences_task

        run_sms_sequences_task.delay()
    return result


async def run_due_sms_sequences(now: datetime | None = None, limit: int = 100) -> dict:
    current = now or datetime.now(UTC)
    processed = sent = stopped = 0
    async with get_db() as db:
        sequences = (
            await db.scalars(
                select(SmsSequence)
                .where(
                    SmsSequence.status == SequenceStatus.ACTIVE.value,
                    SmsSequence.next_due_at <= current,
                )
                .with_for_update(skip_locked=True)
                .limit(limit)
            )
        ).all()
        for sequence in sequences:
            processed += 1
            contact = await db.get(Contact, sequence.contact_id)
            listing = await db.get(Listing, sequence.listing_id)
            campaign = (
                await db.get(Campaign, sequence.campaign_id) if sequence.campaign_id else None
            )
            if not contact or not listing or not campaign:
                sequence.status = SequenceStatus.CANCELLED.value
                stopped += 1
                continue
            if contact.status != ContactStatus.ACTIVE.value or await is_blacklisted(
                contact.phone_e164
            ):
                sequence.status = SequenceStatus.CANCELLED.value
                stopped += 1
                continue
            step = sequence.current_step + 1
            if step >= len(SEQUENCE_DELAYS_DAYS):
                sequence.status = SequenceStatus.COMPLETED.value
                stopped += 1
                continue
            custom_templates = (
                (
                    await db.execute(
                        select(CampaignMessageTemplate).where(
                            CampaignMessageTemplate.campaign_id == campaign.id,
                            CampaignMessageTemplate.channel == "sms",
                            CampaignMessageTemplate.step == step,
                            CampaignMessageTemplate.enabled.is_(True),
                        )
                    )
                )
                .scalars()
                .all()
            )
            if custom_templates:
                selected = custom_templates[
                    hashlib.sha256(f"{sequence.id}:{step}".encode()).digest()[0]
                    % len(custom_templates)
                ]
                variant_key, template = selected.variant_key, selected.body
            else:
                variant_key, template = choose_sms_variant(step, sequence.id)
            body = render_sms_body(
                template, url=listing.url, title=listing.title or "votre véhicule"
            )
            sims = await boundaries.get_sim_list()
            allowed = {}
            if listing.sector_id:
                allowed = {
                    row.sim_id: row.daily_limit
                    for row in (
                        await db.execute(
                            select(SectorSim).where(SectorSim.sector_id == listing.sector_id)
                        )
                    ).scalars()
                }
            today = current.replace(hour=0, minute=0, second=0, microsecond=0)
            eligible_sims = []
            for item in sims:
                if item.get("status") != "active" or (allowed and item["id"] not in allowed):
                    continue
                used = await db.scalar(
                    select(func.count(SmsLog.id)).where(
                        SmsLog.sim_id == item["id"],
                        SmsLog.direction == SmsDirection.OUTBOUND.value,
                        SmsLog.sent_at >= today,
                    )
                )
                quota = min(campaign.quota_per_sim, allowed.get(item["id"], campaign.quota_per_sim))
                if (used or 0) < quota:
                    eligible_sims.append(item)
            sim = eligible_sims[0] if eligible_sims else None
            if sim is None:
                continue
            key = f"sequence:{sequence.id}:{step}"
            existing = await db.scalar(select(SmsLog.id).where(SmsLog.idempotency_key == key))
            if existing:
                sequence.current_step = step
                next_template = None
                if step + 1 < len(SEQUENCE_DELAYS_DAYS):
                    next_template = (
                        await db.execute(
                            select(CampaignMessageTemplate).where(
                                CampaignMessageTemplate.campaign_id == campaign.id,
                                CampaignMessageTemplate.channel == "sms",
                                CampaignMessageTemplate.step == step + 1,
                                CampaignMessageTemplate.enabled.is_(True),
                            )
                        )
                    ).scalar_one_or_none()
                sequence.next_due_at = (
                    _template_due(next_template, sequence.created_at or current)
                    if next_template
                    else next_due_at(step + 1, sequence.created_at or current)
                    if step + 1 < len(SEQUENCE_DELAYS_DAYS)
                    else None
                )
                sequence.status = (
                    SequenceStatus.COMPLETED.value
                    if sequence.next_due_at is None
                    else SequenceStatus.ACTIVE.value
                )
                continue
            try:
                result = await boundaries.send_sms(sim["id"], contact.phone_e164, body)
                if result.status != SmsStatus.SENT:
                    continue
                db.add(
                    SmsLog(
                        sim_id=sim["id"],
                        to_phone=contact.phone_e164,
                        listing_id=listing.id,
                        contact_id=contact.id,
                        campaign_id=campaign.id,
                        body=body,
                        status=SmsStatus.SENT,
                        direction=SmsDirection.OUTBOUND.value,
                        sequence_step=step,
                        variant_key=variant_key,
                        idempotency_key=key,
                        cost_eur=result.cost,
                    )
                )
                sequence.current_step = step
                next_step = step + 1
                next_template = None
                if next_step < len(SEQUENCE_DELAYS_DAYS):
                    next_template = (
                        await db.execute(
                            select(CampaignMessageTemplate).where(
                                CampaignMessageTemplate.campaign_id == campaign.id,
                                CampaignMessageTemplate.channel == "sms",
                                CampaignMessageTemplate.step == next_step,
                                CampaignMessageTemplate.enabled.is_(True),
                            )
                        )
                    ).scalar_one_or_none()
                sequence.next_due_at = (
                    _template_due(next_template, sequence.created_at or current)
                    if next_template
                    else next_due_at(next_step, sequence.created_at or current)
                    if next_step < len(SEQUENCE_DELAYS_DAYS)
                    else None
                )
                sequence.status = (
                    SequenceStatus.COMPLETED.value
                    if sequence.next_due_at is None
                    else SequenceStatus.ACTIVE.value
                )
                sent += 1
            except Exception:
                continue
    return {"processed": processed, "sent": sent, "stopped": stopped}


async def stop_contact_sequences(contact_id: uuid.UUID, status: ContactStatus) -> None:
    async with get_db() as db:
        await db.execute(
            update(Contact).where(Contact.id == contact_id).values(status=status.value)
        )
        await db.execute(
            update(SmsSequence)
            .where(
                SmsSequence.contact_id == contact_id,
                SmsSequence.status == SequenceStatus.ACTIVE.value,
            )
            .values(status=SequenceStatus.CANCELLED.value, next_due_at=None)
        )
