"""
Pydantic models (API I/O + boundaries return types).
SQLAlchemy ORM tables sont dans app/tables.py.
"""
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ── ENUMS ─────────────────────────────────────────────────────────────────────

class AccountStatus(str, Enum):
    EN_CREATION = "EN_CRÉATION"
    EN_CHAUFFE = "EN_CHAUFFE"
    ACTIF = "ACTIF"
    RALENTI = "RALENTI"
    BLOQUE = "BLOQUÉ"
    QUARANTAINE = "QUARANTAINE"


class DatadomeTrustLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class SmsStatus(str, Enum):
    SENT = "sent"
    FAILED = "failed"
    QUEUED = "queued"


class ListingSource(str, Enum):
    LBC = "leboncoin"
    LA_CENTRALE = "la_centrale"


class ListingStatus(str, Enum):
    NOUVELLE = "NOUVELLE"
    SMS_ENVOYE = "SMS_ENVOYÉ"
    REPONSE = "RÉPONSE"
    TRAITE = "TRAITÉ"
    ARCHIVE = "ARCHIVÉ"


class CampaignStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ── BOUNDARIES RETURN TYPES ────────────────────────────────────────────────────

class SmsResult(BaseModel):
    id: str
    status: SmsStatus
    cost: float
    sim_id: str
    to: str


class ActivationOrder(BaseModel):
    id: str
    phone: str
    country: str
    service: str
    cost: float
    expires: int  # unix timestamp


class ProxyInfo(BaseModel):
    url: str           # http://user:pass@host:port
    asn_org: str = ""  # "Orange", "SFR", "Bouygues", "Free Mobile"
    country: str = "FR"


# ── API REQUEST / RESPONSE ─────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str          # "ok" | "degraded"
    db: bool
    redis: bool
    ts: int              # unix timestamp


class ListingOut(BaseModel):
    id: UUID
    source: ListingSource
    url: str
    title: str
    price: int | None = None
    km: int | None = None
    location: str | None = None
    phone: str | None = None
    status: ListingStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class CampaignCreate(BaseModel):
    type: str = Field(..., description="'sms_direct' ou 'lbc_message'")
    message_template: str
    quota_per_sim: int = Field(15, ge=1, le=60)
    listing_ids: list[UUID] = []


class CampaignListingsPayload(BaseModel):
    """Payload pour POST /campaigns/{id}/listings — pré-assigne des annonces."""
    listing_ids: list[UUID] = Field(..., min_length=1)


class CampaignOut(BaseModel):
    id: UUID
    type: str
    status: CampaignStatus
    sent: int = 0
    failed: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class AccountOut(BaseModel):
    id: UUID
    status: AccountStatus
    datadome_trust_level: DatadomeTrustLevel
    score_sante: int
    quota_actuel: int
    erreurs_24h: int
    date_creation: datetime
    derniere_action: datetime | None = None

    model_config = {"from_attributes": True}


# ── WEBHOOK PAYLOADS ───────────────────────────────────────────────────────────

class SmsWebhookPayload(BaseModel):
    sim_id: str
    from_: str = Field(..., alias="from")
    body: str
    ts: int

    model_config = {"populate_by_name": True}


class EmailWebhookPayload(BaseModel):
    recipient: str
    sender: str
    subject: str
    body_plain: str = Field("", alias="body-plain")

    model_config = {"populate_by_name": True}


class CallWebhookPayload(BaseModel):
    sim_id: str
    from_: str = Field(..., alias="from")
    timestamp: int

    model_config = {"populate_by_name": True}


# ── WEBSOCKET EVENTS ───────────────────────────────────────────────────────────

class IncomingCallEvent(BaseModel):
    event: str = "incoming_call"
    caller: str
    listing: dict[str, Any] | None = None
