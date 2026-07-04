"""add campaign scheduling and error tracking

Revision ID: d4f7c2a9b8e1
Revises: c8a6f4d1e2b3
Create Date: 2026-06-30
"""
from alembic import op
import sqlalchemy as sa

revision = "d4f7c2a9b8e1"
down_revision = "c8a6f4d1e2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS scheduled_at TIMESTAMPTZ"))
    op.execute(sa.text("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS last_error TEXT"))


def downgrade() -> None:
    op.drop_column("campaigns", "last_error")
    op.drop_column("campaigns", "scheduled_at")
