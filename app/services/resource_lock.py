"""Atomic claims for sector resources."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, update

from app.db import get_db
from app.tables import SectorAccount, SectorProxy, SectorSim

_RESOURCE_TABLES = {
    "account": SectorAccount,
    "sim": SectorSim,
    "proxy": SectorProxy,
}


async def claim_resource(kind: str, resource_id: UUID, owner: str, ttl_seconds: int = 300) -> bool:
    table = _RESOURCE_TABLES[kind]
    now = datetime.now(UTC)
    async with get_db() as db:
        result = await db.execute(
            update(table)
            .where(
                table.id == resource_id,
                or_(
                    table.locked_until.is_(None),
                    table.locked_until < now,
                    table.locked_by == owner,
                ),
            )
            .values(locked_until=now + timedelta(seconds=ttl_seconds), locked_by=owner)
            .returning(table.id)
        )
        return result.scalar_one_or_none() is not None


async def release_resource(kind: str, resource_id: UUID, owner: str) -> None:
    table = _RESOURCE_TABLES[kind]
    async with get_db() as db:
        await db.execute(
            update(table)
            .where(table.id == resource_id, table.locked_by == owner)
            .values(locked_until=None, locked_by=None)
        )
