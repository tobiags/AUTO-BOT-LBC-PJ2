"""add cancelled campaign status

Revision ID: f6b2d8e4a1c3
Revises: e5a1c7d9f3b2
"""

from alembic import op

revision = "f6b2d8e4a1c3"
down_revision = "e5a1c7d9f3b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE campaign_status ADD VALUE IF NOT EXISTS 'CANCELLED'")


def downgrade() -> None:
    # PostgreSQL cannot remove an enum value without recreating the type.
    pass
