"""
SQLAlchemy ORM — définitions des tables.
Aligné sur le schéma du Cahier Technique Projet 2.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models import (
    AccountStatus,
    CampaignStatus,
    DatadomeTrustLevel,
    ListingSource,
    ListingStatus,
    SmsStatus,
)


class PlatformAccount(Base):
    """Comptes LeBonCoin gérés par le système."""
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
    datadome_cookie: Mapped[bytes | None] = mapped_column(LargeBinary)  # chiffré AES-256
    datadome_cookie_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    session_path: Mapped[str | None] = mapped_column(String(500))       # Patchright user_data_dir
    score_sante: Mapped[int] = mapped_column(Integer, default=100)
    quota_actuel: Mapped[int] = mapped_column(Integer, default=10)      # messages/jour
    erreurs_24h: Mapped[int] = mapped_column(Integer, default=0)
    date_creation: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    derniere_action: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Listing(Base):
    """Annonces collectées sur LBC et La Centrale."""
    __tablename__ = "listings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(
        Enum(ListingSource, name="listing_source"), nullable=False
    )
    url: Mapped[str] = mapped_column(String(1000), unique=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    price: Mapped[int | None] = mapped_column(Integer)                  # euros
    km: Mapped[int | None] = mapped_column(Integer)
    location: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(30))
    raw_data: Mapped[str | None] = mapped_column(Text)                  # JSON brut
    # Attributs véhicule — enrichis depuis l'API /finder/search ou scraping détail
    make: Mapped[str | None] = mapped_column(String(100), index=True)
    model: Mapped[str | None] = mapped_column(String(100), index=True)
    year: Mapped[int | None] = mapped_column(Integer, index=True)
    fuel: Mapped[str | None] = mapped_column(String(50))
    transmission: Mapped[str | None] = mapped_column(String(50))
    # Analyse marché — calculée par vehicle_analyzer
    price_score: Mapped[float | None] = mapped_column(Float)           # % sous marché
    market_avg_price: Mapped[int | None] = mapped_column(Integer)
    market_sample_size: Mapped[int | None] = mapped_column(Integer)
    ai_summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        Enum(ListingStatus, name="listing_status"), default=ListingStatus.NOUVELLE
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SmsLog(Base):
    """Journal de tous les SMS envoyés."""
    __tablename__ = "sms_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sim_id: Mapped[str] = mapped_column(String(50), nullable=False)
    to_phone: Mapped[str] = mapped_column(String(30), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(SmsStatus, name="sms_status"), nullable=False
    )
    project: Mapped[str] = mapped_column(String(10), default="P2")
    cost_eur: Mapped[float | None] = mapped_column(Float)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Blacklist(Base):
    """Numéros STOP — cross-projets P1 + P2."""
    __tablename__ = "blacklist"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    source_sim: Mapped[str | None] = mapped_column(String(50))
    source_project: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Campaign(Base):
    """Campagnes SMS."""
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(String(50), nullable=False)       # sms_direct | lbc_message
    message_template: Mapped[str] = mapped_column(Text, nullable=False)
    quota_per_sim: Mapped[int] = mapped_column(Integer, default=15)
    status: Mapped[str] = mapped_column(
        Enum(CampaignStatus, name="campaign_status"), default=CampaignStatus.PENDING
    )
    sent: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class WebhookEvent(Base):
    """Garantit l'idempotence des webhooks entrants (règle R12)."""
    __tablename__ = "webhook_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)     # sms | email | call
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
