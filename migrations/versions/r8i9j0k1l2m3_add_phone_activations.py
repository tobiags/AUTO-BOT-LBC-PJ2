"""Add temporary phone activation lifecycle tracking."""

import sqlalchemy as sa
from alembic import op

revision = "r8i9j0k1l2m3"
down_revision = "q7h8i9j0k1l2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "phone_activations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False, server_default="smsapp"),
        sa.Column("provider_order_id", sa.String(length=160), nullable=False),
        sa.Column("phone_e164", sa.String(length=30), nullable=False),
        sa.Column("country", sa.String(length=80), nullable=False),
        sa.Column("service", sa.String(length=80), nullable=False),
        sa.Column("cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="reserved"),
        sa.Column("origin", sa.String(length=20), nullable=False, server_default="automatic"),
        sa.Column("platform_account_id", sa.UUID(), nullable=True),
        sa.Column("workflow_id", sa.String(length=160), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_sms", sa.Text(), nullable=True),
        sa.Column("received_code", sa.String(length=20), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["platform_account_id"], ["platform_accounts.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_order_id"),
    )
    op.create_index("ix_phone_activations_phone_e164", "phone_activations", ["phone_e164"])
    op.create_index("ix_phone_activations_status", "phone_activations", ["status"])
    op.create_index("ix_phone_activations_expires_at", "phone_activations", ["expires_at"])
    op.create_index(
        "ix_phone_activations_platform_account_id",
        "phone_activations",
        ["platform_account_id"],
    )
    op.create_index("ix_phone_activations_workflow_id", "phone_activations", ["workflow_id"])


def downgrade() -> None:
    op.drop_index("ix_phone_activations_workflow_id", table_name="phone_activations")
    op.drop_index("ix_phone_activations_platform_account_id", table_name="phone_activations")
    op.drop_index("ix_phone_activations_expires_at", table_name="phone_activations")
    op.drop_index("ix_phone_activations_status", table_name="phone_activations")
    op.drop_index("ix_phone_activations_phone_e164", table_name="phone_activations")
    op.drop_table("phone_activations")
