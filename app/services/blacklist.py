"""
Gestion de la blacklist STOP — cross-projets P1 + P2.
Règle R02 : un STOP reçu n'importe où blackliste dans les deux projets.
"""
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db import get_db
from app.tables import Blacklist


async def add_to_blacklist(phone: str, source_sim: str = "", source_project: str = "P2") -> None:
    """INSERT idempotent — ON CONFLICT DO NOTHING (règle R12)."""
    async with get_db() as db:
        stmt = (
            insert(Blacklist)
            .values(phone=phone, source_sim=source_sim, source_project=source_project)
            .on_conflict_do_nothing(index_elements=["phone"])
        )
        await db.execute(stmt)


async def is_blacklisted(phone: str) -> bool:
    async with get_db() as db:
        result = await db.execute(
            select(Blacklist.id).where(Blacklist.phone == phone).limit(1)
        )
        return result.scalar() is not None


async def get_blacklist_count() -> int:
    async with get_db() as db:
        from sqlalchemy import func
        result = await db.execute(select(func.count()).select_from(Blacklist))
        return result.scalar() or 0
