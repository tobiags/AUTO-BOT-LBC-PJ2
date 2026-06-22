"""
Polling automatique des soldes services externes.
Tourne en background toutes les 30 minutes.

Services couverts :
- iProxy    : GET https://iproxy.online/api/console/v1/me       → .balance
- BrowserUse: GET https://api.browser-use.com/api/v3/balance    → .credits
- Anthropic : pas d'API publique — on suit le coût en tokens via claude.py
"""
import asyncio
import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import get_settings
from app.db import get_db
from app.tables import ServiceBalance

log = logging.getLogger(__name__)
_INTERVAL = 30 * 60  # 30 min


async def _upsert_balance(service: str, label: str, balance: float | None,
                           currency: str, low_threshold: float) -> None:
    is_low = balance is not None and balance < low_threshold
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
                last_updated=datetime.now(UTC),
            )
            .on_conflict_do_update(
                index_elements=["service"],
                set_={
                    "balance": balance,
                    "is_low": is_low,
                    "last_updated": datetime.now(UTC),
                },
            )
        )
        await db.commit()

    log.info("Balance updated: %s = %s %s (low=%s)", service, balance, currency, is_low)


async def _poll_iproxy(client: httpx.AsyncClient, api_key: str) -> None:
    try:
        resp = await client.get(
            "https://iproxy.online/api/console/v1/me",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        balance = float(data.get("balance") or 0)
        await _upsert_balance("iproxy", "iProxy SIMs", balance, "EUR", 5.0)
    except Exception as exc:
        log.warning("iProxy balance poll failed: %s", exc)


async def _poll_browseruse(client: httpx.AsyncClient, api_key: str) -> None:
    try:
        # Endpoint billing v2 — seul endpoint documenté qui retourne le solde
        resp = await client.get(
            "https://api.browser-use.com/api/v2/billing/account",
            headers={"X-Browser-Use-API-Key": api_key},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        # totalCreditsBalanceUsd = somme mensuel + top-up
        balance = float(data.get("totalCreditsBalanceUsd") or 0)
        await _upsert_balance("browseruse", "BrowserUse", balance, "USD", 5.0)
    except Exception as exc:
        log.warning("BrowserUse balance poll failed: %s", exc)


async def _poll_once() -> None:
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        tasks = []
        if settings.iproxy_api_key:
            tasks.append(_poll_iproxy(client, settings.iproxy_api_key))
        else:
            log.debug("IPROXY_API_KEY manquant — poll ignoré")

        if settings.browser_use_api_key:
            tasks.append(_poll_browseruse(client, settings.browser_use_api_key))
        else:
            log.debug("BROWSER_USE_API_KEY manquant — poll ignoré")

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


async def start_balance_poller() -> None:
    """Lance la boucle de polling en arrière-plan."""
    log.info("Balance poller démarré (intervalle %ds)", _INTERVAL)
    # Premier poll immédiat au démarrage
    await _poll_once()
    while True:
        await asyncio.sleep(_INTERVAL)
        await _poll_once()
