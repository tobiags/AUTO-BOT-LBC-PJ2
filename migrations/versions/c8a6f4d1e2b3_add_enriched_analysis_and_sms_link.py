"""add enriched analysis fields and sms_log listing link

Revision ID: c8a6f4d1e2b3
Revises: b3d2e5f9a1c7
Create Date: 2026-06-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'c8a6f4d1e2b3'
down_revision = 'b3d2e5f9a1c7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TABLE listings ADD COLUMN IF NOT EXISTS reliability_score INTEGER"))
    op.execute(sa.text("ALTER TABLE listings ADD COLUMN IF NOT EXISTS known_issues_json TEXT"))
    op.execute(sa.text("ALTER TABLE listings ADD COLUMN IF NOT EXISTS inspection_tips_json TEXT"))
    op.execute(sa.text("ALTER TABLE listings ADD COLUMN IF NOT EXISTS negotiation_tip TEXT"))
    op.execute(sa.text("ALTER TABLE sms_log ADD COLUMN IF NOT EXISTS listing_id UUID"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_sms_log_listing_id ON sms_log (listing_id)"))


def downgrade() -> None:
    op.drop_index('ix_sms_log_listing_id', table_name='sms_log')
    op.drop_column('sms_log', 'listing_id')
    op.drop_column('listings', 'negotiation_tip')
    op.drop_column('listings', 'inspection_tips_json')
    op.drop_column('listings', 'known_issues_json')
    op.drop_column('listings', 'reliability_score')
