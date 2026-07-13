"""
Polling automatique des soldes services externes.
Tourne en background toutes les 30 minutes.

Services couverts :
- iProxy    : GET /api/cn/v1 -> état de la connexion et expiration du plan
- BrowserUse: GET /api/v2/billing/account -> totalCreditsBalanceUsd +
  subscriptionCurrentPeriodEnd
- Anthropic : pas d'API publique - suivi via tokens dans anthropic_tracker.py
"""
import asyncio
import logging
from datetime import UTC, datetime

import httpx
import sentry_sdk
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import get_settings
from app.db import get_db
from app.models import BalanceUpdateEvent
from app.tables import ServiceBalance
from app.ws import ws_manager

log = logging.getLogger(__name__)
_INTERVAL = 30 * 60  # 30 min


async def _upsert_balance(
    service: str,
    label: str,
    balance: float | None,
    currency: str,
    low_threshold: float,
    expires_at: datetime | None = None,
    ) -> None:
    is_low = balance is not None and balance < low_threshold
    now = datetime.now(UTC)
    async with get_db() as db:
        await db.execute(
            pg_insert(ServiceBalance)
            .values(
                service=service,
                label=label,
                balance=balance,
                currency=currency,
                is_low=is_low,
                low_threshold=low_threshold,
                last_updated=now,
                expires_at=expires_at,
            )
            .on_conflict_do_update(
                index_elements=["service"],
                set_={
                    "balance": balance,
                    "is_low": is_low,
                    "last_updated": now,
                    "expires_at": expires_at,
                },
            )
        )
        await db.commit()
    log.info("Balance updated: %s = %s %s expires=%s", service, balance, currency, expires_at)
    await ws_manager.broadcast(
        BalanceUpdateEvent(
            service=service,
            label=label,
            balance=balance,
            currency=currency,
            is_low=is_low,
            low_threshold=low_threshold,
            last_updated=now,
            expires_at=expires_at,
        ).model_dump()
    )
    if is_low:
        sentry_sdk.capture_message(
            f"Low balance detected for {service}: {balance} {currency}",
            level="warning",
        )


async def _poll_iproxy(
    client: httpx.AsyncClient,
    api_key: str,
    connection_id: str,
) -> None:
    try:
        conn = (
            await client.get(
                "https://iproxy.online/api/cn/v1",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
        ).raise_for_status().json()
        expires_str = conn.get("plan_info", {}).get("active_plan", {}).get("expires_at")
        expires_at = (
            datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
            if expires_str
            else None
        )

        balance_raw = conn.get("balance")
        balance = float(balance_raw) if balance_raw is not None else None
        await _upsert_balance("iproxy", f"iProxy {connection_id}", balance, "USD", 5.0, expires_at)
    except Exception as exc:
        log.warning("iProxy balance poll failed: %s", exc)
        sentry_sdk.capture_exception(exc)


async def _poll_browseruse(client: httpx.AsyncClient, api_key: str) -> None:
    try:
        resp = await client.get(
            "https://api.browser-use.com/api/v2/billing/account",
            headers={"X-Browser-Use-API-Key": api_key},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        balance = float(data.get("totalCreditsBalanceUsd") or 0)
        period_end = data.get("planInfo", {}).get("subscriptionCurrentPeriodEnd")
        expires_at = datetime.fromisoformat(period_end) if period_end else None
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        await _upsert_balance("browseruse", "BrowserUse", balance, "USD", 5.0, expires_at)
    except Exception as exc:
        log.warning("BrowserUse balance poll failed: %s", exc)
        sentry_sdk.capture_exception(exc)


async def _poll_once() -> None:
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        tasks = []
        if settings.iproxy_api_key and settings.iproxy_connection_id:
            tasks.append(
                _poll_iproxy(
                    client,
                    settings.iproxy_api_key,
                    settings.iproxy_connection_id,
                )
            )
        if settings.browser_use_api_key:
            tasks.append(_poll_browseruse(client, settings.browser_use_api_key))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


async def start_balance_poller() -> None:
    """Lance la boucle de polling en arriere-plan."""
    log.info("Balance poller demarre (intervalle %ds)", _INTERVAL)
    await _poll_once()
    while True:
        await asyncio.sleep(_INTERVAL)
        await _poll_once()
