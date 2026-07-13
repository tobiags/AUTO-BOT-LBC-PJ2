"""Add contacts, inbound SMS history and scheduled SMS sequences."""

from alembic import op
import sqlalchemy as sa


revision = "j0b2c3d4e5f"
down_revision = "i9a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE sms_status ADD VALUE IF NOT EXISTS 'received'")
    op.create_table(
        "contacts",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("phone_e164", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("last_classification", sa.String(30)),
        sa.Column("last_inbound_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("phone_e164", name="uq_contacts_phone_e164"),
    )
    op.add_column("listings", sa.Column("contact_id", sa.UUID(), sa.ForeignKey("contacts.id")))
    op.create_index("ix_listings_contact_id", "listings", ["contact_id"])
    for name, column in (
        ("contact_id", sa.Column("contact_id", sa.UUID(), sa.ForeignKey("contacts.id"))),
        ("direction", sa.Column("direction", sa.String(20), nullable=False, server_default="outbound")),
        ("sequence_step", sa.Column("sequence_step", sa.Integer())),
        ("variant_key", sa.Column("variant_key", sa.String(80))),
        ("classification", sa.Column("classification", sa.String(30))),
        ("idempotency_key", sa.Column("idempotency_key", sa.String(160))),
        ("received_at", sa.Column("received_at", sa.DateTime(timezone=True))),
    ):
        op.add_column("sms_log", column)
    op.create_index("ix_sms_log_contact_id", "sms_log", ["contact_id"])
    op.create_unique_constraint("uq_sms_log_idempotency_key", "sms_log", ["idempotency_key"])
    op.create_table(
        "sms_sequences",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("contact_id", sa.UUID(), sa.ForeignKey("contacts.id"), nullable=False),
        sa.Column("listing_id", sa.UUID(), sa.ForeignKey("listings.id"), nullable=False),
        sa.Column("campaign_id", sa.UUID(), sa.ForeignKey("campaigns.id")),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="-1"),
        sa.Column("next_due_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("listing_id", "campaign_id", name="uq_sms_sequence_listing_campaign"),
    )
    op.create_index("ix_sms_sequences_contact_id", "sms_sequences", ["contact_id"])
    op.create_index("ix_sms_sequences_listing_id", "sms_sequences", ["listing_id"])
    op.create_index("ix_sms_sequences_campaign_id", "sms_sequences", ["campaign_id"])


def downgrade() -> None:
    op.drop_index("ix_sms_sequences_campaign_id", table_name="sms_sequences")
    op.drop_index("ix_sms_sequences_listing_id", table_name="sms_sequences")
    op.drop_index("ix_sms_sequences_contact_id", table_name="sms_sequences")
    op.drop_table("sms_sequences")
    op.drop_constraint("uq_sms_log_idempotency_key", "sms_log", type_="unique")
    op.drop_index("ix_sms_log_contact_id", table_name="sms_log")
    for name in ("received_at", "idempotency_key", "classification", "variant_key", "sequence_step", "direction", "contact_id"):
        op.drop_column("sms_log", name)
    op.drop_index("ix_listings_contact_id", table_name="listings")
    op.drop_column("listings", "contact_id")
    op.drop_table("contacts")
