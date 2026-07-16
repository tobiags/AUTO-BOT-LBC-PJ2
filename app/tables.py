"""
SQLAlchemy ORM - definitions des tables.
Aligne sur le schema du Cahier Technique Projet 2.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models import (
    AccountStatus,
    CampaignStatus,
    ConnectorState,
    DatadomeTrustLevel,
    EmailIdentityStatus,
    LbcMessageDirection,
    LbcMessageStatus,
    ListingSource,
    ListingStatus,
    SmsStatus,
    WorkflowStatus,
)


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkspaceSetting(Base):
    __tablename__ = "workspace_settings"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_workspace_settings_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True, nullable=False
    )
    key: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(100))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("workspace_id", "email", name="uq_users_workspace_email"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), index=True, nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False, default="operateur")
    password_hash: Mapped[str | None] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Sector(Base):
    __tablename__ = "sectors"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_sectors_workspace_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    region: Mapped[str] = mapped_column(String(120), nullable=False)
    department: Mapped[str] = mapped_column(String(10), nullable=False)
    radius_km: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    brand_model: Mapped[str | None] = mapped_column(String(120))
    mileage_max: Mapped[int | None] = mapped_column(Integer)
    price_min: Mapped[int | None] = mapped_column(Integer)
    price_max: Mapped[int | None] = mapped_column(Integer)
    frequency_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    schedule_start: Mapped[str] = mapped_column(String(5), default="06:00", nullable=False)
    schedule_end: Mapped[str] = mapped_column(String(5), default="22:00", nullable=False)
    daily_volume: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="actif", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SectorAccount(Base):
    __tablename__ = "sector_accounts"
    __table_args__ = (UniqueConstraint("sector_id", "account_id", name="uq_sector_accounts"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sectors.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("platform_accounts.id", ondelete="CASCADE"), nullable=False
    )
    daily_limit: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(100))


class SectorSim(Base):
    __tablename__ = "sector_sims"
    __table_args__ = (UniqueConstraint("sector_id", "sim_id", name="uq_sector_sims"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sectors.id", ondelete="CASCADE"), nullable=False
    )
    sim_id: Mapped[str] = mapped_column(String(50), nullable=False)
    daily_limit: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(100))


class SectorProxy(Base):
    __tablename__ = "sector_proxies"
    __table_args__ = (UniqueConstraint("sector_id", "proxy_id", name="uq_sector_proxies"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sectors.id", ondelete="CASCADE"), nullable=False
    )
    proxy_id: Mapped[str] = mapped_column(String(120), nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(100))


class CollectionRun(Base):
    __tablename__ = "collection_runs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sectors.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)
    checkpoint: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    listings_seen: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PlatformAccount(Base):
    """Comptes LeBonCoin geres par le systeme."""

    __tablename__ = "platform_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    phone_otp: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(
        Enum(AccountStatus, name="account_status"), default=AccountStatus.EN_CREATION
    )
    datadome_trust_level: Mapped[str] = mapped_column(
        Enum(DatadomeTrustLevel, name="datadome_trust_level"), default=DatadomeTrustLevel.LOW
    )
    datadome_cookie: Mapped[bytes | None] = mapped_column(LargeBinary)
    datadome_cookie_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    session_path: Mapped[str | None] = mapped_column(String(500))
    browser_use_profile_id: Mapped[str | None] = mapped_column(String(100))
    browser_use_session_id: Mapped[str | None] = mapped_column(String(100))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    score_sante: Mapped[int] = mapped_column(Integer, default=100)
    quota_actuel: Mapped[int] = mapped_column(Integer, default=10)
    erreurs_24h: Mapped[int] = mapped_column(Integer, default=0)
    date_creation: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    derniere_action: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EmailIdentity(Base):
    __tablename__ = "email_identities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(
            EmailIdentityStatus,
            name="email_identity_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=EmailIdentityStatus.AVAILABLE,
        nullable=False,
        index=True,
    )
    reserved_by: Mapped[str | None] = mapped_column(String(120))
    reserved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Listing(Base):
    """Annonces collectees sur LBC et La Centrale."""

    __tablename__ = "listings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(Enum(ListingSource, name="listing_source"), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), unique=True, nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    sector_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sectors.id"), index=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), index=True
    )
    title: Mapped[str | None] = mapped_column(String(500))
    price: Mapped[int | None] = mapped_column(Integer)
    km: Mapped[int | None] = mapped_column(Integer)
    location: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(30))
    raw_data: Mapped[str | None] = mapped_column(Text)
    make: Mapped[str | None] = mapped_column(String(100), index=True)
    model: Mapped[str | None] = mapped_column(String(100), index=True)
    year: Mapped[int | None] = mapped_column(Integer, index=True)
    fuel: Mapped[str | None] = mapped_column(String(50))
    transmission: Mapped[str | None] = mapped_column(String(50))
    price_score: Mapped[float | None] = mapped_column(Float)
    market_avg_price: Mapped[int | None] = mapped_column(Integer)
    market_sample_size: Mapped[int | None] = mapped_column(Integer)
    reliability_score: Mapped[int | None] = mapped_column(Integer)
    ai_summary: Mapped[str | None] = mapped_column(Text)
    known_issues_json: Mapped[str | None] = mapped_column(Text)
    inspection_tips_json: Mapped[str | None] = mapped_column(Text)
    negotiation_tip: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        Enum(ListingStatus, name="listing_status"), default=ListingStatus.NOUVELLE
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SmsLog(Base):
    """Journal de tous les SMS envoyes."""

    __tablename__ = "sms_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sim_id: Mapped[str] = mapped_column(String(50), nullable=False)
    to_phone: Mapped[str] = mapped_column(String(30), nullable=False)
    listing_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(
            SmsStatus,
            name="sms_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    project: Mapped[str] = mapped_column(String(10), default="P2")
    cost_eur: Mapped[float | None] = mapped_column(Float)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), index=True
    )
    direction: Mapped[str] = mapped_column(String(20), default="outbound", nullable=False)
    sequence_step: Mapped[int | None] = mapped_column(Integer)
    variant_key: Mapped[str | None] = mapped_column(String(80))
    classification: Mapped[str | None] = mapped_column(String(30))
    idempotency_key: Mapped[str | None] = mapped_column(String(160), unique=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Blacklist(Base):
    """Numeros STOP - cross-projets P1 + P2."""

    __tablename__ = "blacklist"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    source_sim: Mapped[str | None] = mapped_column(String(50))
    source_project: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Campaign(Base):
    """Campagnes SMS."""

    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    message_template: Mapped[str] = mapped_column(Text, nullable=False)
    quota_per_sim: Mapped[int] = mapped_column(Integer, default=15)
    search_criteria: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(CampaignStatus, name="campaign_status"), default=CampaignStatus.PENDING
    )
    sent: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CampaignMessageTemplate(Base):
    """Message éditable depuis le dashboard pour une étape donnée."""

    __tablename__ = "campaign_message_templates"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id", "channel", "step", "variant_key", name="uq_campaign_template_variant"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(String(10), nullable=False)
    step: Mapped[int] = mapped_column(Integer, nullable=False)
    variant_key: Mapped[str] = mapped_column(String(30), nullable=False, default="a")
    delay_days: Mapped[int] = mapped_column(Integer, nullable=False)
    send_time: Mapped[str] = mapped_column(String(5), default="10:00", nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ServiceBalance(Base):
    """Solde des services externes."""

    __tablename__ = "service_balance"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    balance: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="EUR")
    is_low: Mapped[bool] = mapped_column(Boolean, default=False)
    low_threshold: Mapped[float] = mapped_column(Float, default=10.0)
    last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WebhookEvent(Base):
    """Garantit l'idempotence des webhooks entrants."""

    __tablename__ = "webhook_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkflowRun(Base):
    """Etat persistant d'un workflow pilotable depuis le dashboard."""

    __tablename__ = "workflow_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    workflow_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(50))
    target_id: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus, name="workflow_status"),
        default=WorkflowStatus.PENDING,
        nullable=False,
    )
    progress_current: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_total: Mapped[int | None] = mapped_column(Integer)
    batch_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    batch_size: Mapped[int | None] = mapped_column(Integer)
    celery_task_id: Mapped[str | None] = mapped_column(String(100))
    checkpoint: Mapped[dict | None] = mapped_column(JSON)
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    last_error: Mapped[str | None] = mapped_column(Text)
    initiated_by: Mapped[str | None] = mapped_column(String(100))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ConnectorStatus(Base):
    """Dernier etat verifie d'un connecteur externe."""

    __tablename__ = "connector_status"

    name: Mapped[str] = mapped_column(String(50), primary_key=True)
    status: Mapped[ConnectorState] = mapped_column(
        Enum(
            ConnectorState,
            name="connector_state",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    configured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_summary: Mapped[str | None] = mapped_column(String(300))
    details: Mapped[dict | None] = mapped_column(JSON)


class AuditEvent(Base):
    """Trace sans secret des commandes operateur."""

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    action: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(50))
    target_id: Mapped[str | None] = mapped_column(String(100))
    idempotency_key: Mapped[str | None] = mapped_column(String(100), index=True)
    input_summary: Mapped[dict | None] = mapped_column(JSON)
    result_status: Mapped[str] = mapped_column(String(30), nullable=False)
    workflow_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_runs.id"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LbcMessageLog(Base):
    """Journal minimal des messages LBC sans contenu prive complet."""

    __tablename__ = "lbc_message_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_key: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    listing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("listings.id"), index=True
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("platform_accounts.id"), index=True
    )
    direction: Mapped[LbcMessageDirection] = mapped_column(
        Enum(
            LbcMessageDirection,
            name="lbc_message_direction",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    status: Mapped[LbcMessageStatus] = mapped_column(
        Enum(
            LbcMessageStatus,
            name="lbc_message_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    content_hash: Mapped[str | None] = mapped_column(String(64))
    preview: Mapped[str | None] = mapped_column(String(160))
    sequence_step: Mapped[int | None] = mapped_column(Integer)
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    phone_extracted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Contact(Base):
    """Contact vendeur, partagé entre annonces et canaux."""

    __tablename__ = "contacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone_e164: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    last_classification: Mapped[str | None] = mapped_column(String(30))
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SmsSequence(Base):
    """Etat idempotent de la séquence initiale + relances."""

    __tablename__ = "sms_sequences"
    __table_args__ = (
        UniqueConstraint("listing_id", "campaign_id", name="uq_sms_sequence_listing_campaign"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False, index=True
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("listings.id"), nullable=False, index=True
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id"), index=True
    )
    current_step: Mapped[int] = mapped_column(Integer, default=-1, nullable=False)
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CallLog(Base):
    """Historique des appels entrants et qualification opérateur."""

    __tablename__ = "call_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone_e164: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    sim_id: Mapped[str | None] = mapped_column(String(50))
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), index=True
    )
    listing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("listings.id"), index=True
    )
    result: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)
    external_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    called_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
