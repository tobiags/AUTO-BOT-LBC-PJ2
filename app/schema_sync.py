"""
Migrations legeres de compatibilite pour les instances deja deployees.

Le projet n'a pas encore de systeme Alembic; on ajoute donc les colonnes
strictement necessaires de maniere idempotente au demarrage.
"""
from sqlalchemy import text

from app.db import engine

_DDL = [
    "ALTER TABLE listings ADD COLUMN IF NOT EXISTS reliability_score INTEGER",
    "ALTER TABLE listings ADD COLUMN IF NOT EXISTS known_issues_json TEXT",
    "ALTER TABLE listings ADD COLUMN IF NOT EXISTS inspection_tips_json TEXT",
    "ALTER TABLE listings ADD COLUMN IF NOT EXISTS negotiation_tip TEXT",
    "ALTER TABLE sms_log ADD COLUMN IF NOT EXISTS listing_id UUID",
    "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS scheduled_at TIMESTAMPTZ",
    "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS last_error TEXT",
    # service_balance existait en prod sans expires_at
    "ALTER TABLE service_balance ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ",
]


async def ensure_runtime_schema() -> None:
    async with engine.begin() as conn:
        for statement in _DDL:
            await conn.execute(text(statement))
