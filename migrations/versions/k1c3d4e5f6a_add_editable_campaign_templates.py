"""Add dashboard-editable campaign message templates."""

from alembic import op
import sqlalchemy as sa


revision = "k1c3d4e5f6a"
down_revision = "j0b2c3d4e5f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("webhook_events", sa.Column("payload", sa.JSON()))
    for table in ("sector_accounts", "sector_sims", "sector_proxies"):
        op.add_column(table, sa.Column("locked_until", sa.DateTime(timezone=True)))
        op.add_column(table, sa.Column("locked_by", sa.String(100)))
    op.add_column("lbc_message_log", sa.Column("sequence_step", sa.Integer()))
    op.add_column("lbc_message_log", sa.Column("next_due_at", sa.DateTime(timezone=True)))
    op.create_table(
        "campaign_message_templates",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column(
            "campaign_id",
            sa.UUID(),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("variant_key", sa.String(30), nullable=False, server_default="a"),
        sa.Column("delay_days", sa.Integer(), nullable=False),
        sa.Column("send_time", sa.String(5), nullable=False, server_default="10:00"),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "campaign_id", "channel", "step", "variant_key", name="uq_campaign_template_variant"
        ),
    )
    op.create_index(
        "ix_campaign_message_templates_campaign_id", "campaign_message_templates", ["campaign_id"]
    )


def downgrade() -> None:
    op.drop_column("webhook_events", "payload")
    for table in ("sector_proxies", "sector_sims", "sector_accounts"):
        op.drop_column(table, "locked_by")
        op.drop_column(table, "locked_until")
    op.drop_column("lbc_message_log", "next_due_at")
    op.drop_column("lbc_message_log", "sequence_step")
    op.drop_index(
        "ix_campaign_message_templates_campaign_id", table_name="campaign_message_templates"
    )
    op.drop_table("campaign_message_templates")
