"""
Pydantic models (API I/O + boundaries return types).
SQLAlchemy ORM tables sont dans app/tables.py.
"""
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

# ── ENUMS ─────────────────────────────────────────────────────────────────────

class AccountStatus(StrEnum):
    EN_CREATION = "EN_CRÉATION"
    EN_CHAUFFE = "EN_CHAUFFE"
    ACTIF = "ACTIF"
    RALENTI = "RALENTI"
    BLOQUE = "BLOQUÉ"
    QUARANTAINE = "QUARANTAINE"


class DatadomeTrustLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class SmsStatus(StrEnum):
    SENT = "sent"
    FAILED = "failed"
    QUEUED = "queued"


class ListingSource(StrEnum):
    LBC = "leboncoin"
    LA_CENTRALE = "la_centrale"


class ListingStatus(StrEnum):
    NOUVELLE = "NOUVELLE"
    SMS_ENVOYE = "SMS_ENVOYÉ"
    REPONSE = "RÉPONSE"
    TRAITE = "TRAITÉ"
    ARCHIVE = "ARCHIVÉ"


class CampaignStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class WorkflowStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ConnectorState(StrEnum):
    DISABLED = "disabled"
    UNVERIFIED = "unverified"
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"
    MISCONFIGURED = "misconfigured"


class LbcMessageDirection(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class LbcMessageStatus(StrEnum):
    QUEUED = "queued"
    SENT = "sent"
    RECEIVED = "received"
    FAILED = "failed"
    SKIPPED = "skipped"


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


class ConnectorProbeResult(BaseModel):
    name: str
    status: ConnectorState
    configured: bool
    latency_ms: int | None = None
    error_code: str | None = None
    error_summary: str | None = None
    details: dict[str, Any] | None = None


# ── API REQUEST / RESPONSE ─────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str          # "ok" | "degraded"
    db: bool
    redis: bool
    ts: int              # unix timestamp


class HealthCheckComponent(BaseModel):
    name: str
    status: str          #  ok | degraded | down | disabled | misconfigured
    required: bool
    configured: bool
    latency_ms: int | None = None
    error: str | None = None


class AdminHealthResponse(BaseModel):
    status: str
    env: str
    app: str
    version: str
    ts: int
    external_checks: bool
    checks: list[HealthCheckComponent]
    summary: dict[str, int]


class ListingOut(BaseModel):
    id: UUID
    source: ListingSource
    url: str
    title: str | None = None
    price: int | None = None
    km: int | None = None
    location: str | None = None
    phone: str | None = None
    make: str | None = None
    model: str | None = None
    year: int | None = None
    fuel: str | None = None
    transmission: str | None = None
    price_score: float | None = None
    market_avg_price: int | None = None
    market_sample_size: int | None = None
    status: ListingStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class VehicleAnalysisOut(BaseModel):
    listing_id: UUID
    listing_url: str
    # Scoring marché (calculé depuis notre DB)
    price_score: float | None = None          # % sous marché ; positif = sous-évalué
    market_avg_price: int | None = None
    market_min_price: int | None = None
    market_max_price: int | None = None
    market_sample_size: int = 0
    confidence: str = "insufficient"          # "high" | "medium" | "low" | "insufficient"
    # Analyse IA Claude
    reliability_score: int | None = None      # 0-100
    ai_summary: str | None = None
    known_issues: list[str] = []
    inspection_tips: list[str] = []
    negotiation_tip: str | None = None


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
    scheduled_at: datetime | None = None
    last_error: str | None = None
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
    browser_use_profile_id: str | None = None
    browser_use_session_id: str | None = None

    model_config = {"from_attributes": True}


# ── WEBHOOK PAYLOADS ───────────────────────────────────────────────────────────

class SmsToolsMessage(BaseModel):
    id: str
    date_utc: str
    sender: str   # numéro expéditeur
    receiver: str # numéro SIM destinataire
    content: str = ""


class SmsToolsWebhookItem(BaseModel):
    webhook_id: str
    webhook_type: str
    message: SmsToolsMessage


class CallToolsMessage(BaseModel):
    id: str
    date_utc: str
    sender: str   # numéro appelant
    receiver: str # numéro SIM


class CallToolsWebhookItem(BaseModel):
    webhook_id: str
    webhook_type: str
    message: CallToolsMessage


class EmailWebhookPayload(BaseModel):
    recipient: str
    sender: str
    subject: str
    body_plain: str = Field("", alias="body-plain")

    model_config = {"populate_by_name": True}


# ── SMSTOOLS FUNDS WEBHOOKS ───────────────────────────────────────────────────

class SmsToolsFundsItem(BaseModel):
    webhook_id: str
    webhook_type: str  # "insufficient_funds" | "funds_purchased"
    funds: dict[str, Any]


# ── DASHBOARD ─────────────────────────────────────────────────────────────────

class ServiceBalanceOut(BaseModel):
    service: str
    label: str
    balance: float | None
    currency: str
    is_low: bool
    low_threshold: float
    last_updated: datetime | None
    expires_at: datetime | None = None

    model_config = {"from_attributes": True}


class DashboardConnector(BaseModel):
    name: str
    status: ConnectorState
    configured: bool
    latency_ms: int | None = None
    last_success_at: datetime | None = None
    last_checked_at: datetime | None = None
    error_code: str | None = None
    error_summary: str | None = None
    details: dict[str, Any] | None = None

    model_config = {"from_attributes": True}


class DashboardActionItem(BaseModel):
    code: str
    severity: str
    title: str
    detail: str
    target: str


class DashboardWorkflow(BaseModel):
    id: UUID
    workflow_type: str
    status: WorkflowStatus
    progress_current: int
    progress_total: int | None
    batch_number: int
    batch_size: int | None
    last_error: str | None
    updated_at: datetime

    model_config = {"from_attributes": True}


class DashboardStats(BaseModel):
    listings_total: int
    listings_today: int
    sms_sent_total: int
    sms_sent_today: int
    calls_total: int
    calls_today: int
    sms_received_total: int
    sms_received_today: int
    accounts_active: int
    accounts_total: int
    campaigns_running: int
    balances: list[ServiceBalanceOut]
    lbc_messages_sent_total: int = 0
    lbc_messages_sent_today: int = 0
    lbc_messages_received_total: int = 0
    lbc_messages_received_today: int = 0
    phones_extracted_total: int = 0
    phones_extracted_today: int = 0
    connectors: list[DashboardConnector] = Field(default_factory=list)
    actions_required: list[DashboardActionItem] = Field(default_factory=list)
    workflows: list[DashboardWorkflow] = Field(default_factory=list)
    generated_at: datetime


class ConnectorCommandRequest(BaseModel):
    action: Literal["probe", "rotate_ip"]
    idempotency_key: str = Field(min_length=8, max_length=100)
    confirmed: bool = False


class ConnectorCommandResponse(BaseModel):
    command_id: UUID
    status: str
    connector: str
    action: str
    detail: dict[str, Any] = Field(default_factory=dict)


class BrowserUseTaskRequest(BaseModel):
    template_id: str
    target_url: HttpUrl
    idempotency_key: str = Field(min_length=8, max_length=100)
    custom_prompt: str | None = Field(default=None, max_length=4000)


class BrowserUseTaskCreated(BaseModel):
    workflow_id: UUID
    status: WorkflowStatus
    template_id: str


class BrowserUseTaskView(BaseModel):
    workflow_id: UUID
    status: WorkflowStatus
    template_id: str
    target_url: str | None
    provider_task_id: str | None
    session_id: str | None
    cost: float | None
    output: str | None
    output_files: list[dict[str, Any]] = Field(default_factory=list)
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class CampaignCommandRequest(BaseModel):
    action: Literal["start", "pause", "resume", "cancel", "retry"]
    idempotency_key: str = Field(min_length=8, max_length=100)


class CampaignCommandResponse(BaseModel):
    campaign_id: UUID
    workflow_id: UUID | None
    status: CampaignStatus
    action: str


class LabRunRequest(BaseModel):
    engine: Literal["camoufox", "obscura", "both"]
    target_url: HttpUrl
    idempotency_key: str = Field(min_length=8, max_length=100)


class LabRunView(BaseModel):
    workflow_id: UUID
    engine: str
    target_url: str | None
    status: WorkflowStatus
    result: dict[str, Any] = Field(default_factory=dict)
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class LbcMessageView(BaseModel):
    id: UUID
    external_key: str
    listing_id: UUID | None
    account_id: UUID | None
    direction: LbcMessageDirection
    status: LbcMessageStatus
    preview: str | None
    phone_extracted: bool
    error_code: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InboxSyncRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=100)


# ── WEBSOCKET EVENTS ───────────────────────────────────────────────────────────

class IncomingCallEvent(BaseModel):
    event: str = "incoming_call"
    caller: str
    listing: dict[str, Any] | None = None


class BalanceUpdateEvent(BaseModel):
    event: str = "balance_update"
    service: str
    label: str
    balance: float | None
    currency: str
    is_low: bool
    low_threshold: float
    last_updated: datetime
    expires_at: datetime | None = None
