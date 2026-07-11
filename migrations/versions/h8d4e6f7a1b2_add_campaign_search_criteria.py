"""add campaign vehicle search criteria

Revision ID: h8d4e6f7a1b2
Revises: g7c3e9f5b2d4
"""

import sqlalchemy as sa
from alembic import op

revision = "h8d4e6f7a1b2"
down_revision = "g7c3e9f5b2d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column(
            "search_criteria",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.alter_column("campaigns", "search_criteria", server_default=None)


def downgrade() -> None:
    op.drop_column("campaigns", "search_criteria")
