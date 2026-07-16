from dataclasses import dataclass
import re
import secrets
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.config import get_settings
from app.db import get_db
from app.models import EmailIdentityStatus
from app.tables import EmailIdentity


_FIRST_NAMES = ("Alice", "Camille", "Chloe", "Emma", "Julien", "Lucas", "Manon", "Marie", "Nicolas", "Thomas")
_LAST_NAMES = ("Bernard", "Dubois", "Durand", "Garcia", "Lefevre", "Martin", "Moreau", "Petit", "Robert", "Roux")


@dataclass(frozen=True)
class GeneratedIdentity:
    first_name: str
    last_name: str
    email: str


def _local_part(value: str) -> str:
    return re.sub(r"[^a-z]", "", value.lower())


def build_identity(domain: str) -> GeneratedIdentity:
    first_name = secrets.choice(_FIRST_NAMES)
    last_name = secrets.choice(_LAST_NAMES)
    suffix = secrets.token_hex(3)
    return GeneratedIdentity(
        first_name=first_name,
        last_name=last_name,
        email=f"{_local_part(first_name)}.{_local_part(last_name)}-{suffix}@{domain}",
    )


async def list_identities() -> list[EmailIdentity]:
    async with get_db() as db:
        rows = await db.scalars(select(EmailIdentity).order_by(EmailIdentity.created_at.desc()))
        return list(rows)


async def generate_batch(count: int) -> list[EmailIdentity]:
    domain = get_settings().operational_domain.strip().lower()
    if not domain:
        raise ValueError("OPERATIONAL_DOMAIN_NOT_CONFIGURED")
    async with get_db() as db:
        identities: list[EmailIdentity] = []
        for _ in range(count):
            generated = build_identity(domain)
            identity = EmailIdentity(
                first_name=generated.first_name,
                last_name=generated.last_name,
                email=generated.email,
                status=EmailIdentityStatus.AVAILABLE,
            )
            db.add(identity)
            identities.append(identity)
        await db.flush()
        return identities


async def command_identity(identity_id: UUID, action: str, actor: str) -> EmailIdentity:
    async with get_db() as db:
        identity = await db.get(EmailIdentity, identity_id, with_for_update=True)
        if identity is None:
            raise LookupError("EMAIL_IDENTITY_NOT_FOUND")
        now = datetime.now(UTC)
        if action == "reserve":
            if identity.status != EmailIdentityStatus.AVAILABLE:
                raise ValueError("IDENTITY_NOT_AVAILABLE")
            identity.status, identity.reserved_by, identity.reserved_at = EmailIdentityStatus.RESERVED, actor, now
        elif action == "release":
            if identity.status != EmailIdentityStatus.RESERVED:
                raise ValueError("IDENTITY_NOT_RESERVED")
            identity.status, identity.reserved_by, identity.reserved_at = EmailIdentityStatus.AVAILABLE, None, None
        elif action == "use":
            if identity.status != EmailIdentityStatus.RESERVED:
                raise ValueError("IDENTITY_NOT_RESERVED")
            identity.status, identity.used_at = EmailIdentityStatus.USED, now
        elif action == "disable":
            identity.status = EmailIdentityStatus.DISABLED
        await db.flush()
        return identity
