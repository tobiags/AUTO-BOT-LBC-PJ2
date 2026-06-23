"""add service_balance table

Revision ID: b3d2e5f9a1c7
Revises: 7f3a8b2e1d4c
Create Date: 2026-06-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'b3d2e5f9a1c7'
down_revision = '7f3a8b2e1d4c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'service_balance',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('service', sa.String(50), nullable=False),
        sa.Column('label', sa.String(100), nullable=False),
        sa.Column('balance', sa.Float, nullable=True),
        sa.Column('currency', sa.String(10), nullable=False, server_default='EUR'),
        sa.Column('is_low', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('low_threshold', sa.Float, nullable=False, server_default='10.0'),
        sa.Column('last_updated', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('service'),
    )


def downgrade() -> None:
    op.drop_table('service_balance')
