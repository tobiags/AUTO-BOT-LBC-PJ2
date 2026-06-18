"""initial schema

Revision ID: 7f3a8b2e1d4c
Revises:
Create Date: 2026-06-18 00:00:00.000000

Crée les 6 tables du projet :
  platform_accounts, listings, sms_log, blacklist, campaigns, webhook_events

Les colonnes véhicule (make, model, year, fuel, transmission) et analyse marché
(price_score, market_avg_price, market_sample_size, ai_summary) sont incluses
dès la migration initiale.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '7f3a8b2e1d4c'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── platform_accounts ─────────────────────────────────────────────────────
    op.create_table(
        'platform_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('phone_otp', sa.String(20), nullable=True),
        sa.Column(
            'status',
            sa.Enum(
                'EN_CRÉATION', 'EN_CHAUFFE', 'ACTIF', 'RALENTI', 'BLOQUÉ', 'QUARANTAINE',
                name='account_status',
            ),
            nullable=False,
            server_default='EN_CRÉATION',
        ),
        sa.Column(
            'datadome_trust_level',
            sa.Enum('LOW', 'MEDIUM', 'HIGH', name='datadome_trust_level'),
            nullable=False,
            server_default='LOW',
        ),
        sa.Column('datadome_cookie', sa.LargeBinary, nullable=True),
        sa.Column('datadome_cookie_updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('session_path', sa.String(500), nullable=True),
        sa.Column('score_sante', sa.Integer, nullable=False, server_default='100'),
        sa.Column('quota_actuel', sa.Integer, nullable=False, server_default='10'),
        sa.Column('erreurs_24h', sa.Integer, nullable=False, server_default='0'),
        sa.Column('date_creation', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('derniere_action', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )

    # ── listings ──────────────────────────────────────────────────────────────
    op.create_table(
        'listings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            'source',
            sa.Enum('leboncoin', 'la_centrale', name='listing_source'),
            nullable=False,
        ),
        sa.Column('url', sa.String(1000), nullable=False),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('price', sa.Integer, nullable=True),
        sa.Column('km', sa.Integer, nullable=True),
        sa.Column('location', sa.String(200), nullable=True),
        sa.Column('phone', sa.String(30), nullable=True),
        sa.Column('raw_data', sa.Text, nullable=True),
        # Attributs véhicule
        sa.Column('make', sa.String(100), nullable=True),
        sa.Column('model', sa.String(100), nullable=True),
        sa.Column('year', sa.Integer, nullable=True),
        sa.Column('fuel', sa.String(50), nullable=True),
        sa.Column('transmission', sa.String(50), nullable=True),
        # Analyse marché
        sa.Column('price_score', sa.Float, nullable=True),
        sa.Column('market_avg_price', sa.Integer, nullable=True),
        sa.Column('market_sample_size', sa.Integer, nullable=True),
        sa.Column('ai_summary', sa.Text, nullable=True),
        sa.Column(
            'status',
            sa.Enum(
                'NOUVELLE', 'SMS_ENVOYÉ', 'RÉPONSE', 'TRAITÉ', 'ARCHIVÉ',
                name='listing_status',
            ),
            nullable=False,
            server_default='NOUVELLE',
        ),
        sa.Column('campaign_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('url'),
    )
    op.create_index('ix_listings_make', 'listings', ['make'])
    op.create_index('ix_listings_model', 'listings', ['model'])
    op.create_index('ix_listings_year', 'listings', ['year'])
    op.create_index('ix_listings_campaign_id', 'listings', ['campaign_id'])

    # ── sms_log ───────────────────────────────────────────────────────────────
    op.create_table(
        'sms_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sim_id', sa.String(50), nullable=False),
        sa.Column('to_phone', sa.String(30), nullable=False),
        sa.Column('body', sa.Text, nullable=False),
        sa.Column(
            'status',
            sa.Enum('sent', 'failed', 'queued', name='sms_status'),
            nullable=False,
        ),
        sa.Column('project', sa.String(10), nullable=False, server_default='P2'),
        sa.Column('cost_eur', sa.Float, nullable=True),
        sa.Column('campaign_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── blacklist ─────────────────────────────────────────────────────────────
    op.create_table(
        'blacklist',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('phone', sa.String(30), nullable=False),
        sa.Column('source_sim', sa.String(50), nullable=True),
        sa.Column('source_project', sa.String(10), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('phone'),
    )

    # ── campaigns ─────────────────────────────────────────────────────────────
    op.create_table(
        'campaigns',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('message_template', sa.Text, nullable=False),
        sa.Column('quota_per_sim', sa.Integer, nullable=False, server_default='15'),
        sa.Column(
            'status',
            sa.Enum('PENDING', 'RUNNING', 'PAUSED', 'COMPLETED', 'FAILED', name='campaign_status'),
            nullable=False,
            server_default='PENDING',
        ),
        sa.Column('sent', sa.Integer, nullable=False, server_default='0'),
        sa.Column('failed', sa.Integer, nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── webhook_events ────────────────────────────────────────────────────────
    op.create_table(
        'webhook_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_key', sa.String(200), nullable=False),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('processed', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_key'),
    )


def downgrade() -> None:
    op.drop_table('webhook_events')
    op.drop_table('campaigns')
    op.drop_table('blacklist')
    op.drop_table('sms_log')
    op.drop_index('ix_listings_campaign_id', table_name='listings')
    op.drop_index('ix_listings_year', table_name='listings')
    op.drop_index('ix_listings_model', table_name='listings')
    op.drop_index('ix_listings_make', table_name='listings')
    op.drop_table('listings')
    op.drop_table('platform_accounts')
    # Drop PostgreSQL enum types explicitly
    op.execute(sa.text('DROP TYPE IF EXISTS campaign_status'))
    op.execute(sa.text('DROP TYPE IF EXISTS sms_status'))
    op.execute(sa.text('DROP TYPE IF EXISTS listing_status'))
    op.execute(sa.text('DROP TYPE IF EXISTS listing_source'))
    op.execute(sa.text('DROP TYPE IF EXISTS datadome_trust_level'))
    op.execute(sa.text('DROP TYPE IF EXISTS account_status'))
