"""
Pydantic models (API I/O + boundaries return types).
SQLAlchemy ORM tables sont dans app/tables.py.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, SecretStr, model_validator

# ── ENUMS ─────────────────────────────────────────────────────────────────────


class AccountStatus(StrEnum):
    EN_CREATION = "EN_CRÉATION"
    EN_CHAUFFE = "EN_CHAUFFE"
    ACTIF = "ACTIF"
    RALENTI = "RALENTI"
    BLOQUE = "BLOQUÉ"
    QUARANTAINE = "QUARANTAINE"


class EmailIdentityStatus(StrEnum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    USED = "used"
    DISABLED = "disabled"


class DatadomeTrustLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class SmsStatus(StrEnum):
    SENT = "sent"
    FAILED = "failed"
    QUEUED = "queued"
    RECEIVED = "received"


class PhoneActivationStatus(StrEnum):
    RESERVED = "reserved"
    WAITING = "waiting"
    RECEIVED = "received"
    USED = "used"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REFUNDED = "refunded"
    FAILED = "failed"


class PhoneActivationOrigin(StrEnum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"


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


class UserRole(StrEnum):
    ADMINISTRATEUR = "administrateur"
    MANAGER = "manager"
    OPERATEUR = "operateur"


class SectorStatus(StrEnum):
    ACTIF = "actif"
    PAUSE = "pause"


class CollectionRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ContactStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    CONVERTED = "converted"
    INVALID = "invalid"
    DO_NOT_CONTACT = "do_not_contact"


class SmsDirection(StrEnum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class SmsClassification(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    STOP = "stop"
    INFORMATION = "information"
    AMBIGUOUS = "ambiguous"
    INVALID = "invalid"


class SequenceStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ApifyAccountStatus(StrEnum):
    ACTIVE = "active"
    INVALID = "invalid"
    SUSPENDED = "suspended"


class ApifyResourceType(StrEnum):
    ACTOR = "actor"
    TASK = "task"


class ApifyRunStatus(StrEnum):
    READY = "READY"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"
    TIMED_OUT = "TIMED-OUT"


class ApifyItemStatus(StrEnum):
    PENDING = "pending"
    IMPORTED = "imported"
    IGNORED = "ignored"
    DUPLICATE = "duplicate"
    EXCEPTION = "exception"


class ApifyProfileStatus(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    RETIRED = "retired"


class ApifyExperimentDecision(StrEnum):
    KEEP = "keep"
    DISCARD = "discard"
    CRASH = "crash"


class ApifyExceptionStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


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
    url: str  # http://user:pass@host:port
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
    status: str  # "ok" | "degraded"
    db: bool
    redis: bool
    ts: int  # unix timestamp


class HealthCheckComponent(BaseModel):
    name: str
    status: str  #  ok | degraded | down | disabled | misconfigured
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
    price_score: float | None = None  # % sous marché ; positif = sous-évalué
    market_avg_price: int | None = None
    market_min_price: int | None = None
    market_max_price: int | None = None
    market_sample_size: int = 0
    confidence: str = "insufficient"  # "high" | "medium" | "low" | "insufficient"
    # Analyse IA Claude
    reliability_score: int | None = None  # 0-100
    ai_summary: str | None = None
    known_issues: list[str] = []
    inspection_tips: list[str] = []
    negotiation_tip: str | None = None


class CampaignCreate(BaseModel):
    type: str = Field(..., description="'sms_direct', 'lbc_message' ou 'both'")
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
    search_criteria: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class AccountOut(BaseModel):
    id: UUID
    email: str
    phone_otp: str | None = None
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


class PhoneActivationOut(BaseModel):
    id: UUID
    provider: str
    provider_order_id: str
    phone_e164: str
    country: str
    service: str
    cost: float
    status: PhoneActivationStatus
    origin: PhoneActivationOrigin
    platform_account_id: UUID | None = None
    workflow_id: str | None = None
    expires_at: datetime
    received_at: datetime | None = None
    used_at: datetime | None = None
    received_sms: str | None = None
    received_code: str | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PhoneActivationCreate(BaseModel):
    country: str | None = Field(default=None, min_length=2, max_length=80)
    service: str = Field(default="leboncoin", min_length=2, max_length=80)


class PhoneActivationPageOut(BaseModel):
    items: list[PhoneActivationOut]
    total: int


class PhoneOperationsSummaryOut(BaseModel):
    active_numbers: int
    received_numbers: int
    expiring_soon: int
    sms_sent: int
    sms_received: int
    sms_failed: int


class SmsMessageOut(BaseModel):
    id: UUID
    direction: str
    phone_e164: str
    sim_id: str
    body: str
    status: str
    project: str
    cost_eur: float | None = None
    campaign_id: UUID | None = None
    contact_id: UUID | None = None
    listing_id: UUID | None = None
    sequence_step: int | None = None
    variant_key: str | None = None
    classification: str | None = None
    occurred_at: datetime


class SmsMessagePageOut(BaseModel):
    items: list[SmsMessageOut]
    total: int


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    display_name: str = Field(min_length=1, max_length=120)
    role: UserRole = UserRole.OPERATEUR


class UserLogin(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    id: UUID
    email: str
    display_name: str
    role: UserRole
    workspace_id: UUID
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserCreated(UserOut):
    temporary_password: str


class SectorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    source: ListingSource
    region: str = Field(min_length=1, max_length=120)
    department: str = Field(min_length=1, max_length=10)
    radius_km: int = Field(0, ge=0, le=500)
    brand_model: str | None = Field(default=None, max_length=120)
    mileage_max: int | None = Field(default=None, ge=0, le=2_000_000)
    price_min: int | None = Field(default=None, ge=0, le=2_000_000)
    price_max: int | None = Field(default=None, ge=0, le=2_000_000)
    frequency_minutes: int = Field(60, ge=5, le=1440)
    schedule_start: str = Field("06:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    schedule_end: str = Field("22:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    daily_volume: int = Field(50, ge=1, le=10000)

    @model_validator(mode="after")
    def validate_prices(self):
        if (
            self.price_min is not None
            and self.price_max is not None
            and self.price_min > self.price_max
        ):
            raise ValueError("price_min must be less than or equal to price_max")
        return self


class SectorOut(SectorCreate):
    id: UUID
    workspace_id: UUID
    status: SectorStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class SectorResourceAssignment(BaseModel):
    account_ids: list[UUID] = []
    proxy_ids: list[str] = []
    sim_ids: list[str] = []
    daily_limit_per_account: int = Field(10, ge=1, le=10000)
    daily_limit_per_sim: int = Field(15, ge=1, le=10000)


class SectorResourcesOut(BaseModel):
    account_ids: list[UUID]
    proxy_ids: list[str]
    sim_ids: list[str]
    daily_limit_per_account: int
    daily_limit_per_sim: int


class WorkspaceSettingUpsert(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,79}$")
    value: dict[str, Any]


class WorkspaceSettingOut(WorkspaceSettingUpsert):
    updated_by: str | None
    updated_at: datetime

    model_config = {"from_attributes": True}


class EmailIdentityOut(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    email: str
    status: EmailIdentityStatus
    reserved_by: str | None = None
    reserved_at: datetime | None = None
    used_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class EmailIdentityBatchRequest(BaseModel):
    count: Literal[10, 15, 20]


class EmailIdentityCommandRequest(BaseModel):
    action: Literal["reserve", "release", "use", "disable"]


class EmailMessageListItemOut(BaseModel):
    id: UUID
    identity_id: UUID
    sender: str
    recipient: str
    subject: str
    received_at: datetime
    read_at: datetime | None

    model_config = {"from_attributes": True}


class EmailMessageOut(EmailMessageListItemOut):
    body_plain: str
    body_html: str


class EmailMessagePageOut(BaseModel):
    items: list[EmailMessageListItemOut]
    total: int


class AuditEventOut(BaseModel):
    id: UUID
    actor: str
    role: str
    action: str
    target_type: str | None
    target_id: str | None
    result_status: str
    input_summary: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SmsSequenceOut(BaseModel):
    id: UUID
    contact_id: UUID
    listing_id: UUID | None
    campaign_id: UUID | None
    current_step: int
    next_due_at: datetime | None
    status: SequenceStatus
    context_json: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class ApifyAccountCreate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    token: SecretStr


class ApifyAccountOut(BaseModel):
    id: UUID
    workspace_id: UUID
    label: str
    apify_user_id: str
    username: str
    token_masked: str
    status: ApifyAccountStatus
    last_checked_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApifyCatalogResource(BaseModel):
    resource_type: ApifyResourceType
    resource_id: str
    name: str
    description: str | None = None
    modified_at: datetime | None = None


class ApifyBindingCreate(BaseModel):
    account_id: UUID
    resource_type: Literal["actor", "task"]
    resource_id: str = Field(min_length=1, max_length=255)
    name: str | None = Field(default=None, max_length=255)
    sector_id: UUID | None = None
    campaign_id: UUID
    input: dict[str, Any] = Field(default_factory=dict)
    schedule_authority: Literal["internal", "apify"] = "internal"
    schedule_minutes: int | None = Field(default=60, ge=5, le=10080)

    @model_validator(mode="after")
    def validate_schedule(self):
        if self.schedule_authority == "internal" and self.schedule_minutes is None:
            raise ValueError(
                "internal scheduling authority requires schedule_minutes"
            )
        if self.schedule_authority == "apify" and self.schedule_minutes is not None:
            raise ValueError("Apify scheduling authority forbids schedule_minutes")
        return self


class ApifyBindingOut(BaseModel):
    id: UUID
    workspace_id: UUID
    account_id: UUID
    sector_id: UUID | None = None
    campaign_id: UUID | None = None
    resource_type: ApifyResourceType
    resource_id: str
    name: str
    enabled: bool
    schedule_authority: Literal["internal", "apify"]
    schedule_minutes: int | None = None
    next_run_at: datetime | None = None
    webhook_id: str | None = None
    schema_fingerprint: str | None = None
    active_profile_id: UUID | None = None
    suspended_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApifyRunOut(BaseModel):
    id: UUID
    workspace_id: UUID
    account_id: UUID
    binding_id: UUID
    apify_run_id: str
    status: ApifyRunStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    default_dataset_id: str | None = None
    cost_usd: float | None = None
    items_read: int = 0
    items_imported: int = 0
    items_ignored: int = 0
    items_exception: int = 0
    last_error: str | None = None
    imported_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApifyRunPage(BaseModel):
    items: list[ApifyRunOut]
    total: int
    limit: int
    offset: int


class ApifyItemOut(BaseModel):
    id: UUID
    workspace_id: UUID
    account_id: UUID
    run_id: UUID
    dataset_index: int
    content_hash: str
    raw_payload: dict[str, Any]
    normalized_payload: dict[str, Any] | None = None
    confidence: float | None = None
    status: ApifyItemStatus
    contact_id: UUID | None = None
    listing_id: UUID | None = None
    sms_sequence_id: UUID | None = None
    error: str | None = None
    processed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApifyItemPage(BaseModel):
    items: list[ApifyItemOut]
    total: int
    limit: int
    offset: int


class ApifyProfileView(BaseModel):
    id: UUID
    workspace_id: UUID
    binding_id: UUID
    version: int
    schema_fingerprint: str
    mappings: dict[str, Any]
    aliases: dict[str, Any]
    priorities: dict[str, Any]
    thresholds: dict[str, Any]
    metrics: dict[str, Any]
    status: ApifyProfileStatus
    created_at: datetime
    promoted_at: datetime | None = None
    retired_at: datetime | None = None

    model_config = {"from_attributes": True}


class ApifyExperimentView(BaseModel):
    id: UUID
    workspace_id: UUID
    binding_id: UUID
    baseline_profile_id: UUID | None = None
    candidate_profile_id: UUID
    corpus_size: int
    baseline_metrics: dict[str, Any]
    candidate_metrics: dict[str, Any]
    decision: ApifyExperimentDecision | None = None
    reason: str | None = None
    created_at: datetime
    evaluated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ApifyExceptionView(BaseModel):
    id: UUID
    workspace_id: UUID
    binding_id: UUID
    run_id: UUID | None = None
    item_id: UUID | None = None
    category: str
    evidence: dict[str, Any]
    status: ApifyExceptionStatus
    resolution: str | None = None
    resolved_by: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None

    model_config = {"from_attributes": True}


class ApifyWebhookPayload(BaseModel):
    event_type: str = Field(alias="eventType")
    resource: dict[str, Any]
    event_data: dict[str, Any] = Field(default_factory=dict, alias="eventData")

    model_config = {"populate_by_name": True}


class ApifyDashboardSummary(BaseModel):
    accounts_total: int = 0
    accounts_active: int = 0
    bindings_total: int = 0
    bindings_enabled: int = 0
    runs_running: int = 0
    runs_failed: int = 0
    items_imported: int = 0
    exceptions_open: int = 0


class CampaignMessageTemplateUpsert(BaseModel):
    channel: str = Field(pattern=r"^(sms|lbc)$")
    step: int = Field(ge=0, le=20)
    variant_key: str = Field("a", pattern=r"^[a-zA-Z0-9_-]{1,30}$")
    delay_days: int = Field(ge=0, le=365)
    send_time: str = Field("10:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    body: str = Field(min_length=1, max_length=2000)
    enabled: bool = True


class CampaignMessageTemplateOut(CampaignMessageTemplateUpsert):
    id: UUID
    campaign_id: UUID
    updated_at: datetime

    model_config = {"from_attributes": True}


class CallOutcomeUpdate(BaseModel):
    result: str = Field(min_length=1, max_length=50)
    notes: str | None = Field(default=None, max_length=2000)


class ContactLookupOut(BaseModel):
    phone_e164: str
    contact_id: UUID | None
    listings: list[dict[str, Any]]
    calls: list[dict[str, Any]]


# ── WEBHOOK PAYLOADS ───────────────────────────────────────────────────────────


class SmsToolsMessage(BaseModel):
    id: str
    date_utc: str
    sender: str  # numéro expéditeur
    receiver: str  # numéro SIM destinataire
    content: str = ""


class SmsToolsWebhookItem(BaseModel):
    webhook_id: str
    webhook_type: str
    message: SmsToolsMessage


class CallToolsMessage(BaseModel):
    id: str
    date_utc: str
    sender: str  # numéro appelant
    receiver: str  # numéro SIM


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
    accounts_warming: int = 0
    accounts_slowed: int = 0
    accounts_blocked: int = 0
    accounts_quarantined: int = 0
    campaigns_running: int
    balances: list[ServiceBalanceOut]
    lbc_messages_sent_total: int = 0
    lbc_messages_sent_today: int = 0
    lbc_messages_received_total: int = 0
    lbc_messages_received_today: int = 0
    phones_extracted_total: int = 0
    phones_extracted_today: int = 0
    phone_extraction_rate: float = 0
    sms_response_rate: float = 0
    lbc_response_rate: float = 0
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
    live_url: str | None = None
    duration_seconds: float | None = None
    step_count: int = 0
    screenshots: list[str] = Field(default_factory=list)
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class CampaignCommandRequest(BaseModel):
    action: Literal["start", "pause", "resume", "cancel", "retry"]
    idempotency_key: str = Field(min_length=8, max_length=100)


class VehicleSearchCriteria(BaseModel):
    # Compatibilité des campagnes historiques ; ces filtres ne sont plus proposés dans le dashboard.
    brand_model: str | None = Field(default=None, max_length=120)
    vehicle_type: str | None = Field(default=None, max_length=80)
    region: str | None = Field(default=None, max_length=120)
    department: str | None = Field(default=None, max_length=10)
    budget_min: int | None = Field(default=None, ge=0, le=2_000_000)
    budget_max: int | None = Field(default=None, ge=0, le=2_000_000)
    year_max: int | None = Field(default=None, ge=1900, le=2100)
    mileage_max: int | None = Field(default=None, ge=0, le=2_000_000)

    @model_validator(mode="after")
    def validate_budget(self):
        if self.budget_min is not None and self.budget_max is not None:
            if self.budget_min > self.budget_max:
                raise ValueError("budget_min must be less than or equal to budget_max")
        return self


class CampaignCreateCommand(BaseModel):
    type: Literal["sms_direct", "lbc_message", "both"]
    message_template: str = Field(min_length=1, max_length=2000)
    quota_per_sim: int = Field(15, ge=1, le=60)
    search_criteria: VehicleSearchCriteria = Field(default_factory=VehicleSearchCriteria)
    idempotency_key: str = Field(min_length=8, max_length=100)


class AnalyzerCommandRequest(BaseModel):
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


class AccountCommandRequest(BaseModel):
    action: Literal["inspect", "warm", "quarantine", "restore"]
    idempotency_key: str = Field(min_length=8, max_length=100)


class AccountCreateCommandRequest(BaseModel):
    mode: Literal["A", "B"] = "B"
    idempotency_key: str = Field(min_length=8, max_length=100)


class AccountCommandResponse(BaseModel):
    account_id: UUID | None
    workflow_id: UUID
    action: str
    status: str


class WorkflowRunView(BaseModel):
    id: UUID
    workflow_type: str
    target_type: str | None
    target_id: str | None
    status: WorkflowStatus
    progress_current: int
    progress_total: int | None
    batch_number: int
    batch_size: int | None
    checkpoint: dict[str, Any] | None
    last_error_code: str | None
    last_error: str | None
    initiated_by: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowCommandRequest(BaseModel):
    action: Literal["pause", "resume", "cancel", "retry"]
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
