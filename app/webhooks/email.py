"""
Webhook Mailgun → POST /webhooks/email.
Reçoit les emails LBC de vérification.
Règle R12 : idempotent.
"""
import hashlib
import logging
import re

from fastapi import APIRouter, Form
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import get_db
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
):
    event_key = hashlib.sha256(f"email:{recipient}:{sender}:{subject}".encode()).hexdigest()[:32]

    # Idempotence — R12
    async with get_db() as db:
        result = await db.execute(
            pg_insert(WebhookEvent)
            .values(event_key=event_key, source="email", processed=False)
            .on_conflict_do_nothing(index_elements=["event_key"])
            .returning(WebhookEvent.id)
        )
        if result.scalar() is None:
            return {"ok": True, "duplicate": True}

    code = extract_verification_code(body_plain)
    if not code:
        log.warning("Email reçu sans code de vérification — destinataire=%s", recipient)
        return {"ok": True, "code": None}

    log.info("Code LBC extrait : %s — destinataire=%s", code, recipient)

    # Associer le code au compte en attente (EN_CHAUFFE avec cet email)
    async with get_db() as db:
        result = await db.execute(
            select(PlatformAccount).where(PlatformAccount.email == recipient).limit(1)
        )
        account = result.scalar_one_or_none()
        if account:
            log.info("Compte trouvé : id=%s — dépôt code Redis pour Patchright", account.id)
            # Dépose le code en Redis. account_creation._poll_email_code_redis() le récupère.
            import redis.asyncio as _aioredis
            from app.config import get_settings as _gs
            _redis = _aioredis.from_url(_gs().redis_url, decode_responses=True)
            try:
                await _redis.setex(f"email_code:{recipient}", 600, code)
            finally:
                await _redis.aclose()

    return {"ok": True, "code": code}
