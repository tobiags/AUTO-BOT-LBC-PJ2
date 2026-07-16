"""Add the dashboard-managed email identity pool."""

from alembic import op
import sqlalchemy as sa


revision = "o5f6a7b8c9d0"
down_revision = "n4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    status = sa.Enum("available", "reserved", "used", "disabled", name="email_identity_status")
    status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "email_identities",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("first_name", sa.String(length=80), nullable=False),
        sa.Column("last_name", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("status", status, nullable=False, server_default="available"),
        sa.Column("reserved_by", sa.String(length=120), nullable=True),
        sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_email_identities_status", "email_identities", ["status"])


def downgrade() -> None:
    op.drop_index("ix_email_identities_status", table_name="email_identities")
    op.drop_table("email_identities")
    sa.Enum(name="email_identity_status").drop(op.get_bind(), checkfirst=True)
