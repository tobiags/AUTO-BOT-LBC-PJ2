"""add browser use account profiles

Revision ID: g7c3e9f5b2d4
Revises: f6b2d8e4a1c3
"""

import sqlalchemy as sa
from alembic import op

revision = "g7c3e9f5b2d4"
down_revision = "f6b2d8e4a1c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "platform_accounts",
        sa.Column("browser_use_profile_id", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "platform_accounts",
        sa.Column("browser_use_session_id", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("platform_accounts", "browser_use_session_id")
    op.drop_column("platform_accounts", "browser_use_profile_id")
