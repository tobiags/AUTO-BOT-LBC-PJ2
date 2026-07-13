"""Add shared workspace, sector resources and collection checkpoints."""

from alembic import op
import sqlalchemy as sa


revision = "i9a1b2c3d4e5"
down_revision = "h8d4e6f7a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.UUID(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("role", sa.String(30), nullable=False, server_default="operateur"),
        sa.Column("password_hash", sa.String(255)),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "email", name="uq_users_workspace_email"),
    )
    op.create_index("ix_users_workspace_id", "users", ["workspace_id"])
    op.create_table(
        "sectors",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.UUID(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("region", sa.String(120), nullable=False),
        sa.Column("department", sa.String(10), nullable=False),
        sa.Column("radius_km", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("brand_model", sa.String(120)),
        sa.Column("mileage_max", sa.Integer()),
        sa.Column("price_min", sa.Integer()),
        sa.Column("price_max", sa.Integer()),
        sa.Column("frequency_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("schedule_start", sa.String(5), nullable=False, server_default="06:00"),
        sa.Column("schedule_end", sa.String(5), nullable=False, server_default="22:00"),
        sa.Column("daily_volume", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("status", sa.String(20), nullable=False, server_default="actif"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "name", name="uq_sectors_workspace_name"),
    )
    op.create_index("ix_sectors_workspace_id", "sectors", ["workspace_id"])
    for table, fk, cols, constraint in (
        ("sector_accounts", "account_id", [sa.Column("account_id", sa.UUID(), sa.ForeignKey("platform_accounts.id", ondelete="CASCADE"), nullable=False)], "uq_sector_accounts"),
        ("sector_sims", "sim_id", [sa.Column("sim_id", sa.String(50), nullable=False)], "uq_sector_sims"),
        ("sector_proxies", "proxy_id", [sa.Column("proxy_id", sa.String(120), nullable=False)], "uq_sector_proxies"),
    ):
        extra = [sa.Column("daily_limit", sa.Integer(), nullable=False, server_default="10")] if table != "sector_proxies" else []
        op.create_table(
            table,
            sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
            sa.Column("sector_id", sa.UUID(), sa.ForeignKey("sectors.id", ondelete="CASCADE"), nullable=False),
            *cols,
            *extra,
            sa.UniqueConstraint("sector_id", fk, name=constraint),
        )
    op.create_table(
        "collection_runs",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("sector_id", sa.UUID(), sa.ForeignKey("sectors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("checkpoint", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("listings_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_collection_runs_sector_id", "collection_runs", ["sector_id"])
    op.add_column("listings", sa.Column("content_hash", sa.String(64)))
    op.add_column("listings", sa.Column("sector_id", sa.UUID(), sa.ForeignKey("sectors.id")))
    op.create_index("ix_listings_content_hash", "listings", ["content_hash"], unique=True)
    op.create_index("ix_listings_sector_id", "listings", ["sector_id"])


def downgrade() -> None:
    op.drop_index("ix_listings_sector_id", table_name="listings")
    op.drop_index("ix_listings_content_hash", table_name="listings")
    op.drop_column("listings", "sector_id")
    op.drop_column("listings", "content_hash")
    op.drop_index("ix_collection_runs_sector_id", table_name="collection_runs")
    op.drop_table("collection_runs")
    op.drop_table("sector_proxies")
    op.drop_table("sector_sims")
    op.drop_table("sector_accounts")
    op.drop_index("ix_sectors_workspace_id", table_name="sectors")
    op.drop_table("sectors")
    op.drop_index("ix_users_workspace_id", table_name="users")
    op.drop_table("users")
    op.drop_table("workspaces")
