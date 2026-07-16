"""Add Apify ingestion and generalize SMS targets.

The downgrade is destructive for generic SMS sequences: rows without a
listing are deleted before the historical non-null constraint is restored.
"""

import sqlalchemy as sa
from alembic import op

revision = "q7h8i9j0k1l2"
down_revision = "p6g7h8i9j0k1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "apify_accounts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("apify_user_id", sa.String(length=120), nullable=False),
        sa.Column("username", sa.String(length=120), nullable=False),
        sa.Column("token_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("token_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("webhook_secret_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("webhook_secret_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "label", name="uq_apify_account_label"),
        sa.UniqueConstraint(
            "workspace_id", "token_fingerprint", name="uq_apify_account_token"
        ),
    )
    op.create_index("ix_apify_accounts_workspace_id", "apify_accounts", ["workspace_id"])
    op.create_index("ix_apify_accounts_status", "apify_accounts", ["status"])

    op.create_table(
        "apify_actor_bindings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("sector_id", sa.UUID(), nullable=True),
        sa.Column("campaign_id", sa.UUID(), nullable=True),
        sa.Column("resource_type", sa.String(length=10), nullable=False),
        sa.Column("resource_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "input_ciphertext",
            sa.LargeBinary(),
            nullable=False,
            server_default=sa.text("decode('', 'hex')"),
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "schedule_authority", sa.String(length=10), nullable=False, server_default="internal"
        ),
        sa.Column("schedule_minutes", sa.Integer(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("webhook_id", sa.String(length=120), nullable=True),
        sa.Column("schema_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("active_profile_id", sa.UUID(), nullable=True),
        sa.Column("suspended_reason", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["account_id"], ["apify_accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sector_id"], ["sectors.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id",
            "resource_type",
            "resource_id",
            name="uq_apify_binding_resource",
        ),
    )
    op.create_index(
        "ix_apify_actor_bindings_workspace_id", "apify_actor_bindings", ["workspace_id"]
    )
    op.create_index(
        "ix_apify_actor_bindings_account_id", "apify_actor_bindings", ["account_id"]
    )
    op.create_index(
        "ix_apify_actor_bindings_sector_id", "apify_actor_bindings", ["sector_id"]
    )
    op.create_index(
        "ix_apify_actor_bindings_campaign_id", "apify_actor_bindings", ["campaign_id"]
    )
    op.create_index(
        "ix_apify_actor_bindings_next_run_at", "apify_actor_bindings", ["next_run_at"]
    )
    op.create_index(
        "ix_apify_actor_bindings_active_profile_id",
        "apify_actor_bindings",
        ["active_profile_id"],
    )

    op.create_table(
        "apify_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("binding_id", sa.UUID(), nullable=False),
        sa.Column("apify_run_id", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="READY"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("default_dataset_id", sa.String(length=120), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("items_read", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_imported", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_ignored", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_exception", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["account_id"], ["apify_accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["binding_id"], ["apify_actor_bindings.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "apify_run_id", name="uq_apify_remote_run"),
    )
    for column in (
        "workspace_id",
        "account_id",
        "binding_id",
        "apify_run_id",
        "status",
        "default_dataset_id",
    ):
        op.create_index(f"ix_apify_runs_{column}", "apify_runs", [column])

    op.create_table(
        "apify_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("dataset_index", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("normalized_payload", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("contact_id", sa.UUID(), nullable=True),
        sa.Column("listing_id", sa.UUID(), nullable=True),
        sa.Column("sms_sequence_id", sa.UUID(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["account_id"], ["apify_accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["apify_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["sms_sequence_id"], ["sms_sequences.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id",
            "run_id",
            "dataset_index",
            "content_hash",
            name="uq_apify_dataset_item",
        ),
    )
    for column in (
        "workspace_id",
        "account_id",
        "run_id",
        "status",
        "contact_id",
        "listing_id",
        "sms_sequence_id",
    ):
        op.create_index(f"ix_apify_items_{column}", "apify_items", [column])

    op.create_table(
        "apify_normalization_profiles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("binding_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("schema_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("mappings", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("aliases", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("priorities", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("thresholds", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("metrics", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="candidate"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["binding_id"], ["apify_actor_bindings.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("binding_id", "version", name="uq_apify_profile_version"),
    )
    op.create_index(
        "ix_apify_normalization_profiles_workspace_id",
        "apify_normalization_profiles",
        ["workspace_id"],
    )
    op.create_index(
        "ix_apify_normalization_profiles_binding_id",
        "apify_normalization_profiles",
        ["binding_id"],
    )
    op.create_index(
        "ix_apify_normalization_profiles_status",
        "apify_normalization_profiles",
        ["status"],
    )

    op.create_table(
        "apify_normalization_experiments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("binding_id", sa.UUID(), nullable=False),
        sa.Column("baseline_profile_id", sa.UUID(), nullable=True),
        sa.Column("candidate_profile_id", sa.UUID(), nullable=False),
        sa.Column("corpus_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "baseline_metrics", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")
        ),
        sa.Column(
            "candidate_metrics", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")
        ),
        sa.Column("decision", sa.String(length=20), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["baseline_profile_id"],
            ["apify_normalization_profiles.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["binding_id"], ["apify_actor_bindings.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["candidate_profile_id"],
            ["apify_normalization_profiles.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_apify_normalization_experiments_workspace_id",
        "apify_normalization_experiments",
        ["workspace_id"],
    )
    op.create_index(
        "ix_apify_normalization_experiments_binding_id",
        "apify_normalization_experiments",
        ["binding_id"],
    )
    op.create_index(
        "ix_apify_normalization_experiments_decision",
        "apify_normalization_experiments",
        ["decision"],
    )

    op.create_table(
        "apify_exceptions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("binding_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column("item_id", sa.UUID(), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("resolved_by", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["binding_id"], ["apify_actor_bindings.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["item_id"], ["apify_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["apify_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("workspace_id", "binding_id", "run_id", "item_id", "status"):
        op.create_index(f"ix_apify_exceptions_{column}", "apify_exceptions", [column])

    op.execute(
        """
        DELETE FROM sms_sequences duplicate
        USING sms_sequences keeper
        WHERE duplicate.contact_id = keeper.contact_id
          AND duplicate.campaign_id = keeper.campaign_id
          AND duplicate.created_at > keeper.created_at
        """
    )
    op.drop_constraint(
        "uq_sms_sequence_listing_campaign", "sms_sequences", type_="unique"
    )
    op.alter_column("sms_sequences", "listing_id", nullable=True)
    op.add_column(
        "sms_sequences",
        sa.Column(
            "context_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )
    op.create_unique_constraint(
        "uq_sms_sequence_contact_campaign",
        "sms_sequences",
        ["contact_id", "campaign_id"],
    )


def downgrade() -> None:
    op.execute("DELETE FROM sms_sequences WHERE listing_id IS NULL")
    op.drop_constraint(
        "uq_sms_sequence_contact_campaign", "sms_sequences", type_="unique"
    )
    op.drop_column("sms_sequences", "context_json")
    op.alter_column("sms_sequences", "listing_id", nullable=False)
    op.create_unique_constraint(
        "uq_sms_sequence_listing_campaign",
        "sms_sequences",
        ["listing_id", "campaign_id"],
    )

    op.drop_table("apify_exceptions")
    op.drop_table("apify_normalization_experiments")
    op.drop_table("apify_normalization_profiles")
    op.drop_table("apify_items")
    op.drop_table("apify_runs")
    op.drop_table("apify_actor_bindings")
    op.drop_table("apify_accounts")
