"""Add persisted incoming call history."""

from alembic import op
import sqlalchemy as sa


revision = "l2d4e5f6a7b"
down_revision = "k1c3d4e5f6a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "call_log",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("phone_e164", sa.String(20), nullable=False),
        sa.Column("sim_id", sa.String(50)),
        sa.Column("contact_id", sa.UUID(), sa.ForeignKey("contacts.id")),
        sa.Column("listing_id", sa.UUID(), sa.ForeignKey("listings.id")),
        sa.Column("result", sa.String(50)),
        sa.Column("notes", sa.Text()),
        sa.Column("external_key", sa.String(160), nullable=False),
        sa.Column("called_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("external_key", name="uq_call_log_external_key"),
    )
    op.create_index("ix_call_log_phone_e164", "call_log", ["phone_e164"])
    op.create_index("ix_call_log_contact_id", "call_log", ["contact_id"])
    op.create_index("ix_call_log_listing_id", "call_log", ["listing_id"])


def downgrade() -> None:
    op.drop_index("ix_call_log_listing_id", table_name="call_log")
    op.drop_index("ix_call_log_contact_id", table_name="call_log")
    op.drop_index("ix_call_log_phone_e164", table_name="call_log")
    op.drop_table("call_log")
