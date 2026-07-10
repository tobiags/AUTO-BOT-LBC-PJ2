"""add control tower foundation

Revision ID: e5a1c7d9f3b2
Revises: d4f7c2a9b8e1
Create Date: 2026-07-10
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e5a1c7d9f3b2"
down_revision = "d4f7c2a9b8e1"
branch_labels = None
depends_on = None

workflow_status = sa.Enum(
    "PENDING",
    "RUNNING",
    "PAUSED",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    name="workflow_status",
)
connector_state = sa.Enum(
    "disabled",
    "unverified",
    "ok",
    "degraded",
    "down",
    "misconfigured",
    name="connector_state",
)
lbc_message_direction = sa.Enum("inbound", "outbound", name="lbc_message_direction")
lbc_message_status = sa.Enum(
    "queued",
    "sent",
    "received",
    "failed",
    "skipped",
    name="lbc_message_status",
)


def upgrade() -> None:
    op.create_table(
        "workflow_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("idempotency_key", sa.String(100), nullable=False, unique=True),
        sa.Column("workflow_type", sa.String(50), nullable=False),
        sa.Column("target_type", sa.String(50)),
        sa.Column("target_id", sa.String(100)),
        sa.Column("status", workflow_status, nullable=False),
        sa.Column("progress_current", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_total", sa.Integer()),
        sa.Column("batch_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("batch_size", sa.Integer()),
        sa.Column("celery_task_id", sa.String(100)),
        sa.Column("checkpoint", sa.JSON()),
        sa.Column("last_error_code", sa.String(80)),
        sa.Column("last_error", sa.Text()),
        sa.Column("initiated_by", sa.String(100)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_workflow_runs_workflow_type", "workflow_runs", ["workflow_type"])

    op.create_table(
        "connector_status",
        sa.Column("name", sa.String(50), primary_key=True),
        sa.Column("status", connector_state, nullable=False),
        sa.Column("configured", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_summary", sa.String(300)),
        sa.Column("details", sa.JSON()),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("target_type", sa.String(50)),
        sa.Column("target_id", sa.String(100)),
        sa.Column("idempotency_key", sa.String(100)),
        sa.Column("input_summary", sa.JSON()),
        sa.Column("result_status", sa.String(30), nullable=False),
        sa.Column(
            "workflow_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_runs.id"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_idempotency_key", "audit_events", ["idempotency_key"])
    op.create_index("ix_audit_events_workflow_run_id", "audit_events", ["workflow_run_id"])

    op.create_table(
        "lbc_message_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("external_key", sa.String(150), nullable=False, unique=True),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("listings.id")),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("platform_accounts.id"),
        ),
        sa.Column("direction", lbc_message_direction, nullable=False),
        sa.Column("status", lbc_message_status, nullable=False),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("preview", sa.String(160)),
        sa.Column("phone_extracted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_code", sa.String(80)),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_lbc_message_log_listing_id", "lbc_message_log", ["listing_id"])
    op.create_index("ix_lbc_message_log_account_id", "lbc_message_log", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_lbc_message_log_account_id", table_name="lbc_message_log")
    op.drop_index("ix_lbc_message_log_listing_id", table_name="lbc_message_log")
    op.drop_table("lbc_message_log")
    op.drop_index("ix_audit_events_workflow_run_id", table_name="audit_events")
    op.drop_index("ix_audit_events_idempotency_key", table_name="audit_events")
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("connector_status")
    op.drop_index("ix_workflow_runs_workflow_type", table_name="workflow_runs")
    op.drop_table("workflow_runs")
    lbc_message_status.drop(op.get_bind(), checkfirst=True)
    lbc_message_direction.drop(op.get_bind(), checkfirst=True)
    connector_state.drop(op.get_bind(), checkfirst=True)
    workflow_status.drop(op.get_bind(), checkfirst=True)
