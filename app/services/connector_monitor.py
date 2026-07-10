import time
from datetime import UTC, datetime

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app import boundaries
from app.config import get_settings
from app.db import get_db
from app.models import ConnectorProbeResult, ConnectorState
from app.tables import ConnectorStatus


def _elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def _failure(
    name: str,
    configured: bool,
    started: float,
    exc: Exception,
) -> ConnectorProbeResult:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code in (401, 403):
        state = ConnectorState.MISCONFIGURED
    elif status_code == 429:
        state = ConnectorState.DEGRADED
    else:
        state = ConnectorState.DOWN

    return ConnectorProbeResult(
        name=name,
        status=state,
        configured=configured,
        latency_ms=_elapsed_ms(started),
        error_code=f"HTTP_{status_code}" if status_code else type(exc).__name__,
        error_summary=str(exc)[:300],
    )


async def probe_iproxy() -> ConnectorProbeResult:
    settings = get_settings()
    configured = bool(
        settings.iproxy_api_key
        and settings.iproxy_connection_id
        and settings.iproxy_proxy_id
    )
    if not configured:
        return ConnectorProbeResult(
            name="iproxy",
            status=ConnectorState.DISABLED,
            configured=False,
        )

    started = time.perf_counter()
    try:
        await boundaries.get_4g_proxy()
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        return _failure("iproxy", True, started, exc)

    return ConnectorProbeResult(
        name="iproxy",
        status=ConnectorState.OK,
        configured=True,
        latency_ms=_elapsed_ms(started),
    )


async def probe_smstools() -> ConnectorProbeResult:
    settings = get_settings()
    if not settings.smstools_api_key:
        return ConnectorProbeResult(
            name="smstools",
            status=ConnectorState.DISABLED,
            configured=False,
        )

    started = time.perf_counter()
    try:
        sims = await boundaries.get_sim_list()
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        return _failure("smstools", True, started, exc)

    active = sum(1 for sim in sims if sim.get("status") == "active")
    return ConnectorProbeResult(
        name="smstools",
        status=ConnectorState.OK,
        configured=True,
        latency_ms=_elapsed_ms(started),
        details={"active_sims": active},
    )


async def refresh_connector_statuses() -> list[ConnectorProbeResult]:
    results = [await probe_smstools(), await probe_iproxy()]
    now = datetime.now(UTC)

    async with get_db() as db:
        for result in results:
            last_success = (
                now
                if result.status == ConnectorState.OK
                else ConnectorStatus.last_success_at
            )
            await db.execute(
                pg_insert(ConnectorStatus)
                .values(
                    name=result.name,
                    status=result.status,
                    configured=result.configured,
                    latency_ms=result.latency_ms,
                    last_success_at=(
                        now if result.status == ConnectorState.OK else None
                    ),
                    last_checked_at=now,
                    error_code=result.error_code,
                    error_summary=result.error_summary,
                    details=result.details,
                )
                .on_conflict_do_update(
                    index_elements=["name"],
                    set_={
                        "status": result.status,
                        "configured": result.configured,
                        "latency_ms": result.latency_ms,
                        "last_success_at": last_success,
                        "last_checked_at": now,
                        "error_code": result.error_code,
                        "error_summary": result.error_summary,
                        "details": result.details,
                    },
                )
            )
    return results
