from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, func, or_, select

from app.db import get_db
from app.tables import EmailIdentity, EmailMessage


async def store_inbound_message(
    *, event_key: str, recipient: str, sender: str, subject: str, body_plain: str, body_html: str
) -> bool:
    normalized_recipient = recipient.strip().lower()
    async with get_db() as db:
        identity = await db.scalar(select(EmailIdentity).where(EmailIdentity.email == normalized_recipient))
        if identity is None:
            return False
        db.add(
            EmailMessage(
                identity_id=identity.id,
                event_key=event_key,
                recipient=normalized_recipient,
                sender=sender.strip(),
                subject=subject,
                body_plain=body_plain,
                body_html=body_html,
                expires_at=datetime.now(UTC) + timedelta(days=7),
            )
        )
        return True


async def list_email_messages(
    *, identity_id: UUID | None, query: str | None, unread_only: bool, limit: int, offset: int
) -> tuple[list[EmailMessage], int]:
    conditions = []
    if identity_id is not None:
        conditions.append(EmailMessage.identity_id == identity_id)
    if unread_only:
        conditions.append(EmailMessage.read_at.is_(None))
    if query:
        pattern = f"%{query.strip()}%"
        conditions.append(or_(EmailMessage.sender.ilike(pattern), EmailMessage.subject.ilike(pattern)))
    async with get_db() as db:
        statement = select(EmailMessage).order_by(EmailMessage.received_at.desc())
        count_statement = select(func.count()).select_from(EmailMessage)
        for condition in conditions:
            statement = statement.where(condition)
            count_statement = count_statement.where(condition)
        rows = list((await db.scalars(statement.limit(limit).offset(offset))).all())
        total = int((await db.scalar(count_statement)) or 0)
        return rows, total


async def get_email_message(message_id: UUID) -> EmailMessage | None:
    async with get_db() as db:
        return await db.get(EmailMessage, message_id)


async def mark_email_message_read(message_id: UUID) -> EmailMessage | None:
    async with get_db() as db:
        message = await db.get(EmailMessage, message_id)
        if message is not None and message.read_at is None:
            message.read_at = datetime.now(UTC)
        return message


async def delete_email_message(message_id: UUID) -> bool:
    async with get_db() as db:
        message = await db.get(EmailMessage, message_id)
        if message is None:
            return False
        await db.delete(message)
        return True


async def purge_expired_email_messages(now: datetime | None = None) -> int:
    async with get_db() as db:
        result = await db.execute(delete(EmailMessage).where(EmailMessage.expires_at <= (now or datetime.now(UTC))))
        return result.rowcount or 0
