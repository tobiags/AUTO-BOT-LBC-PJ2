"""GET /api/v1/dashboard — stats globales pour le tableau de bord."""
import logging
from datetime import UTC, datetime

import sentry_sdk
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import get_settings
from app.db import get_db
from app.models import (
    AccountStatus,
    BalanceUpdateEvent,
    CampaignStatus,
    ConnectorState,
    DashboardActionItem,
    DashboardConnector,
    DashboardStats,
    DashboardWorkflow,
    LbcMessageDirection,
    LbcMessageStatus,
    ServiceBalanceOut,
    WorkflowStatus,
)
from app.tables import (
    Campaign,
    ConnectorStatus,
    LbcMessageLog,
    Listing,
    PlatformAccount,
    ServiceBalance,
    SmsLog,
    WebhookEvent,
    WorkflowRun,
)
from app.ws import ws_manager

router = APIRouter(prefix="/api/v1", tags=["dashboard"])
log = logging.getLogger(__name__)

_SERVICES_DEFAULT = [
    {"service": "smstools",   "label": "SMSTools SMS",     "low_threshold": 10.0},
    {"service": "iproxy",     "label": "iProxy SIMs",      "low_threshold": 5.0},
    {"service": "browseruse", "label": "BrowserUse",       "low_threshold": 5.0},
    {"service": "anthropic",  "label": "Anthropic Claude", "low_threshold": 5.0},
]


class BalanceUpdate(BaseModel):
    balance: float
    currency: str = "EUR"


def build_action_items(
    connectors: list[ConnectorStatus],
    *,
    accounts_active: int,
    accounts_minimum: int,
) -> list[DashboardActionItem]:
    actions: list[DashboardActionItem] = []
    for connector in connectors:
        if connector.status in (
            ConnectorState.DOWN,
            ConnectorState.MISCONFIGURED,
        ):
            severity = "critical"
        elif connector.status == ConnectorState.DEGRADED:
            severity = "warning"
        else:
            continue

        code = connector.error_code or connector.status
        actions.append(
            DashboardActionItem(
                code=f"connector.{connector.name}.{code}",
                severity=severity,
                title=f"Connecteur {connector.name} indisponible",
                detail=connector.error_summary or "Verification requise",
                target=connector.name,
            )
        )

    if accounts_active < accounts_minimum:
        actions.append(
            DashboardActionItem(
                code="accounts.pool_below_minimum",
                severity="warning",
                title="Pool de comptes insuffisant",
                detail=(
                    f"{accounts_active} actifs pour un minimum de "
                    f"{accounts_minimum}"
                ),
                target="accounts",
            )
        )

    return sorted(actions, key=lambda item: item.severity != "critical")


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard():
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    async with get_db() as db:
        # ── Annonces ────────────────────────────────────────────────────────
        listings_total = (await db.execute(select(func.count()).select_from(Listing))).scalar() or 0
        listings_today = (await db.execute(
            select(func.count()).select_from(Listing).where(Listing.created_at >= today_start)
        )).scalar() or 0

        # ── SMS envoyés ──────────────────────────────────────────────────────
        sms_total = (await db.execute(select(func.count()).select_from(SmsLog))).scalar() or 0
        sms_today = (await db.execute(
            select(func.count()).select_from(SmsLog).where(SmsLog.sent_at >= today_start)
        )).scalar() or 0

        # ── Appels reçus ─────────────────────────────────────────────────────
        calls_total = (await db.execute(
            select(func.count()).select_from(WebhookEvent).where(WebhookEvent.source == "call")
        )).scalar() or 0
        calls_today = (await db.execute(
            select(func.count()).select_from(WebhookEvent)
            .where(WebhookEvent.source == "call", WebhookEvent.created_at >= today_start)
        )).scalar() or 0

        # ── SMS reçus ────────────────────────────────────────────────────────
        sms_received_total = (await db.execute(
            select(func.count()).select_from(WebhookEvent).where(WebhookEvent.source == "sms")
        )).scalar() or 0
        sms_received_today = (await db.execute(
            select(func.count()).select_from(WebhookEvent)
            .where(WebhookEvent.source == "sms", WebhookEvent.created_at >= today_start)
        )).scalar() or 0

        # -- Messagerie LBC ---------------------------------------------------
        lbc_messages_sent_total = (await db.execute(
            select(func.count()).select_from(LbcMessageLog).where(
                LbcMessageLog.direction == LbcMessageDirection.OUTBOUND,
                LbcMessageLog.status == LbcMessageStatus.SENT,
            )
        )).scalar() or 0
        lbc_messages_sent_today = (await db.execute(
            select(func.count()).select_from(LbcMessageLog).where(
                LbcMessageLog.direction == LbcMessageDirection.OUTBOUND,
                LbcMessageLog.status == LbcMessageStatus.SENT,
                LbcMessageLog.created_at >= today_start,
            )
        )).scalar() or 0
        lbc_messages_received_total = (await db.execute(
            select(func.count()).select_from(LbcMessageLog).where(
                LbcMessageLog.direction == LbcMessageDirection.INBOUND,
                LbcMessageLog.status == LbcMessageStatus.RECEIVED,
            )
        )).scalar() or 0
        lbc_messages_received_today = (await db.execute(
            select(func.count()).select_from(LbcMessageLog).where(
                LbcMessageLog.direction == LbcMessageDirection.INBOUND,
                LbcMessageLog.status == LbcMessageStatus.RECEIVED,
                LbcMessageLog.created_at >= today_start,
            )
        )).scalar() or 0
        phones_extracted_total = (await db.execute(
            select(func.count()).select_from(LbcMessageLog).where(
                LbcMessageLog.phone_extracted.is_(True)
            )
        )).scalar() or 0
        phones_extracted_today = (await db.execute(
            select(func.count()).select_from(LbcMessageLog).where(
                LbcMessageLog.phone_extracted.is_(True),
                LbcMessageLog.created_at >= today_start,
            )
        )).scalar() or 0

        # ── Comptes ──────────────────────────────────────────────────────────
        accounts_total = (
            await db.execute(select(func.count()).select_from(PlatformAccount))
        ).scalar() or 0
        accounts_active = (await db.execute(
            select(func.count()).select_from(PlatformAccount).where(
                PlatformAccount.status.in_([AccountStatus.ACTIF, AccountStatus.EN_CHAUFFE])
            )
        )).scalar() or 0

        # ── Campagnes ────────────────────────────────────────────────────────
        campaigns_running = (await db.execute(
            select(func.count()).select_from(Campaign).where(
                Campaign.status == CampaignStatus.RUNNING
            )
        )).scalar() or 0

        connector_rows = (
            await db.execute(select(ConnectorStatus).order_by(ConnectorStatus.name))
        ).scalars().all()
        workflow_rows = (
            await db.execute(
                select(WorkflowRun)
                .where(WorkflowRun.status.in_([
                    WorkflowStatus.PENDING,
                    WorkflowStatus.RUNNING,
                    WorkflowStatus.PAUSED,
                    WorkflowStatus.FAILED,
                ]))
                .order_by(WorkflowRun.updated_at.desc())
                .limit(10)
            )
        ).scalars().all()
        connectors = [
            DashboardConnector.model_validate(row) for row in connector_rows
        ]
        workflows = [
            DashboardWorkflow.model_validate(row) for row in workflow_rows
        ]
        actions_required = build_action_items(
            connector_rows,
            accounts_active=accounts_active,
            accounts_minimum=get_settings().lbc_accounts_min_active,
        )

        # ── Soldes services ──────────────────────────────────────────────────
        existing = (await db.execute(select(ServiceBalance))).scalars().all()
        existing_map = {b.service: b for b in existing}

        balances = []
        for svc in _SERVICES_DEFAULT:
            if svc["service"] in existing_map:
                balances.append(ServiceBalanceOut.model_validate(existing_map[svc["service"]]))
            else:
                balances.append(ServiceBalanceOut(
                    service=svc["service"],
                    label=svc["label"],
                    balance=None,
                    currency="EUR",
                    is_low=False,
                    low_threshold=svc["low_threshold"],
                    last_updated=None,
                ))

    return DashboardStats(
        listings_total=listings_total,
        listings_today=listings_today,
        sms_sent_total=sms_total,
        sms_sent_today=sms_today,
        calls_total=calls_total,
        calls_today=calls_today,
        sms_received_total=sms_received_total,
        sms_received_today=sms_received_today,
        accounts_active=accounts_active,
        accounts_total=accounts_total,
        campaigns_running=campaigns_running,
        balances=balances,
        lbc_messages_sent_total=lbc_messages_sent_total,
        lbc_messages_sent_today=lbc_messages_sent_today,
        lbc_messages_received_total=lbc_messages_received_total,
        lbc_messages_received_today=lbc_messages_received_today,
        phones_extracted_total=phones_extracted_total,
        phones_extracted_today=phones_extracted_today,
        connectors=connectors,
        actions_required=actions_required,
        workflows=workflows,
        generated_at=datetime.now(UTC),
    )


@router.put("/dashboard/balance/{service}")
async def update_balance(service: str, body: BalanceUpdate):
    """Mise à jour manuelle du solde d'un service (iProxy, BrowserUse, Anthropic…)."""
    svc_info = next((s for s in _SERVICES_DEFAULT if s["service"] == service), None)
    if not svc_info:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Service '{service}' inconnu")

    is_low = body.balance < svc_info["low_threshold"]
    now = datetime.now(UTC)

    async with get_db() as db:
        await db.execute(
            pg_insert(ServiceBalance)
            .values(
                service=service,
                label=svc_info["label"],
                balance=body.balance,
                currency=body.currency,
                is_low=is_low,
                low_threshold=svc_info["low_threshold"],
                last_updated=now,
            )
            .on_conflict_do_update(
                index_elements=["service"],
                set_={
                    "balance": body.balance,
                    "currency": body.currency,
                    "is_low": is_low,
                    "last_updated": now,
                },
            )
        )
        await db.commit()

    if is_low:
        sentry_sdk.capture_message(
            f"Manual low balance update for {service}: {body.balance} {body.currency}",
            level="warning",
        )
    await ws_manager.broadcast(
        BalanceUpdateEvent(
            service=service,
            label=svc_info["label"],
            balance=body.balance,
            currency=body.currency,
            is_low=is_low,
            low_threshold=svc_info["low_threshold"],
            last_updated=now,
        ).model_dump()
    )

    return {"ok": True, "service": service, "balance": body.balance, "is_low": is_low}
