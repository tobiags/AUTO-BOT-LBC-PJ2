"""Allow failed accounts to be removed from the active pool safely."""

from alembic import op
import sqlalchemy as sa


revision = "n4e5f6a7b8c9"
down_revision = "m3e4f5a6b7c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "platform_accounts",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_platform_accounts_deleted_at",
        "platform_accounts",
        ["deleted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_platform_accounts_deleted_at", table_name="platform_accounts")
    op.drop_column("platform_accounts", "deleted_at")
