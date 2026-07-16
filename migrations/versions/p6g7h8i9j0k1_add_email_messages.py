"""Add retained inbound email messages."""

from alembic import op
import sqlalchemy as sa


revision = "p6g7h8i9j0k1"
down_revision = "o5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("identity_id", sa.UUID(), nullable=False),
        sa.Column("event_key", sa.String(length=64), nullable=False),
        sa.Column("sender", sa.String(length=255), nullable=False),
        sa.Column("recipient", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=998), nullable=False, server_default=""),
        sa.Column("body_plain", sa.Text(), nullable=False, server_default=""),
        sa.Column("body_html", sa.Text(), nullable=False, server_default=""),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["identity_id"], ["email_identities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_key"),
    )
    op.create_index("ix_email_messages_identity_received", "email_messages", ["identity_id", "received_at"])
    op.create_index("ix_email_messages_expires_at", "email_messages", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_email_messages_expires_at", table_name="email_messages")
    op.drop_index("ix_email_messages_identity_received", table_name="email_messages")
    op.drop_table("email_messages")
