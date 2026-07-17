"""Normalize legacy uppercase sms_status labels to application values."""

from alembic import op

revision = "s9j0k1l2m3n4"
down_revision = "r8i9j0k1l2m3"
branch_labels = None
depends_on = None


def _rename_if_needed(old: str, new: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_type type
                JOIN pg_enum value ON value.enumtypid = type.oid
                WHERE type.typname = 'sms_status' AND value.enumlabel = '{old}'
            ) AND NOT EXISTS (
                SELECT 1
                FROM pg_type type
                JOIN pg_enum value ON value.enumtypid = type.oid
                WHERE type.typname = 'sms_status' AND value.enumlabel = '{new}'
            ) THEN
                ALTER TYPE sms_status RENAME VALUE '{old}' TO '{new}';
            END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    _rename_if_needed("SENT", "sent")
    _rename_if_needed("FAILED", "failed")
    _rename_if_needed("QUEUED", "queued")
    _rename_if_needed("RECEIVED", "received")


def downgrade() -> None:
    _rename_if_needed("sent", "SENT")
    _rename_if_needed("failed", "FAILED")
    _rename_if_needed("queued", "QUEUED")
    _rename_if_needed("received", "RECEIVED")
