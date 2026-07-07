"""add service_balance table

Revision ID: b3d2e5f9a1c7
Revises: 7f3a8b2e1d4c
Create Date: 2026-06-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'b3d2e5f9a1c7'
down_revision = '7f3a8b2e1d4c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS service_balance (
            id UUID NOT NULL,
            service VARCHAR(50) NOT NULL,
            label VARCHAR(100) NOT NULL,
            balance DOUBLE PRECISION,
            currency VARCHAR(10) NOT NULL DEFAULT 'EUR',
            is_low BOOLEAN NOT NULL DEFAULT false,
            low_threshold DOUBLE PRECISION NOT NULL DEFAULT 10.0,
            last_updated TIMESTAMPTZ,
            expires_at TIMESTAMPTZ,
            PRIMARY KEY (id),
            UNIQUE (service)
        )
    """))
    # Si la table existait déjà sans expires_at, on l'ajoute
    op.execute(sa.text(
        "ALTER TABLE service_balance ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ"
    ))


def downgrade() -> None:
    op.drop_table('service_balance')
