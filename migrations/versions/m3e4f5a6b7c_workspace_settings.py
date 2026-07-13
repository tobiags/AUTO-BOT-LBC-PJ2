"""Add workspace settings for dashboard administration."""

from alembic import op
import sqlalchemy as sa

revision = "m3e4f5a6b7c"
down_revision = "l2d4e5f6a7b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_settings",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.UUID(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.String(100)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "key", name="uq_workspace_settings_key"),
    )
    op.create_index("ix_workspace_settings_workspace_id", "workspace_settings", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_workspace_settings_workspace_id", table_name="workspace_settings")
    op.drop_table("workspace_settings")
