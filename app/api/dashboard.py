"""GET /api/v1/dashboard — stats globales pour le tableau de bord."""
import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import get_db
from app.models import AccountStatus, CampaignStatus, DashboardStats, ServiceBalanceOut
from app.tables import (
    Campaign,
    Listing,
    PlatformAccount,
    ServiceBalance,
    SmsLog,
    WebhookEvent,
)

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

        # ── Comptes ──────────────────────────────────────────────────────────
        accounts_total = (await db.execute(select(func.count()).select_from(PlatformAccount))).scalar() or 0
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
                set_={"balance": body.balance, "currency": body.currency,
                      "is_low": is_low, "last_updated": now},
            )
        )
        await db.commit()

    return {"ok": True, "service": service, "balance": body.balance, "is_low": is_low}
