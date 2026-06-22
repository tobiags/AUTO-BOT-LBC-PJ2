"""service_balance: add expires_at column

Revision ID: a2c1d4e8f3b9
Revises: 7f3a8b2e1d4c
Create Date: 2026-06-22
"""
from alembic import op
import sqlalchemy as sa

revision = 'a2c1d4e8f3b9'
down_revision = '7f3a8b2e1d4c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'service_balance',
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('service_balance', 'expires_at')
