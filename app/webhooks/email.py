"""Signed Mailgun webhook used during LBC account verification."""
import hashlib
import logging
import re

from fastapi import APIRouter, Form
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import get_db
from app.security import verify_mailgun_signature
from app.services.email_inbox import store_inbound_message
from app.tables import PlatformAccount, WebhookEvent

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = logging.getLogger(__name__)
_CODE_RE = re.compile(r"\b\d{5,8}\b")


def extract_verification_code(body: str) -> str | None:
    match = _CODE_RE.search(body)
    return match.group() if match else None


@router.post("/email")
async def receive_email(
    recipient: str = Form(...),
    sender: str = Form(...),
    subject: str = Form(""),
    body_plain: str = Form("", alias="body-plain"),
    body_html: str = Form("", alias="body-html"),
    timestamp: str = Form(...),
    token: str = Form(...),
    signature: str = Form(...),
):
    verify_mailgun_signature(timestamp, token, signature)
    event_key = hashlib.sha256(
        f"email:{recipient}:{sender}:{subject}:{timestamp}:{token}".encode()
    ).hexdigest()[:32]

    async with get_db() as db:
        result = await db.execute(
            pg_insert(WebhookEvent)
            .values(event_key=event_key, source="email", processed=False)
            .on_conflict_do_nothing(index_elements=["event_key"])
            .returning(WebhookEvent.id)
        )
        if result.scalar() is None:
            return {"ok": True, "duplicate": True}

    await store_inbound_message(
        event_key=event_key,
        recipient=recipient,
        sender=sender,
        subject=subject,
        body_plain=body_plain,
        body_html=body_html,
    )

    code = extract_verification_code(body_plain)
    if not code:
        log.warning("Email recu sans code de verification pour destinataire=%s", recipient)
        return {"ok": True}

    async with get_db() as db:
        result = await db.execute(
            select(PlatformAccount).where(PlatformAccount.email == recipient).limit(1)
        )
        account = result.scalar_one_or_none()
        if account:
            import redis.asyncio as aioredis

            from app.config import get_settings

            redis = aioredis.from_url(get_settings().redis_url, decode_responses=True)
            try:
                await redis.setex(f"email_code:{recipient}", 600, code)
            finally:
                await redis.aclose()
        else:
            log.warning("Aucun compte en creation pour destinataire=%s", recipient)

    return {"ok": True}
