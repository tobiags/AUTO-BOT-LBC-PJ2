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
    op.add_column('listings', sa.Column('reliability_score', sa.Integer(), nullable=True))
    op.add_column('listings', sa.Column('known_issues_json', sa.Text(), nullable=True))
    op.add_column('listings', sa.Column('inspection_tips_json', sa.Text(), nullable=True))
    op.add_column('listings', sa.Column('negotiation_tip', sa.Text(), nullable=True))
    op.add_column('sms_log', sa.Column('listing_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index('ix_sms_log_listing_id', 'sms_log', ['listing_id'])


def downgrade() -> None:
    op.drop_index('ix_sms_log_listing_id', table_name='sms_log')
    op.drop_column('sms_log', 'listing_id')
    op.drop_column('listings', 'negotiation_tip')
    op.drop_column('listings', 'inspection_tips_json')
    op.drop_column('listings', 'known_issues_json')
    op.drop_column('listings', 'reliability_score')
