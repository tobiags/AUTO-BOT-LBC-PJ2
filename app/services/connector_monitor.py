import asyncio
import time
from datetime import UTC, datetime

import httpx
import redis.asyncio as aioredis
import sentry_sdk
from sqlalchemy import text
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


async def probe_database() -> ConnectorProbeResult:
    from app.db import engine

    started = time.perf_counter()
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        return _failure("database", True, started, exc)
    return ConnectorProbeResult(
        name="database", status=ConnectorState.OK, configured=True,
        latency_ms=_elapsed_ms(started),
    )


async def probe_redis() -> ConnectorProbeResult:
    settings = get_settings()
    started = time.perf_counter()
    client = aioredis.from_url(settings.redis_url)
    try:
        await asyncio.wait_for(client.ping(), timeout=2)
    except Exception as exc:
        return _failure("redis", True, started, exc)
    finally:
        await client.aclose()
    return ConnectorProbeResult(
        name="redis", status=ConnectorState.OK, configured=True,
        latency_ms=_elapsed_ms(started),
    )


async def probe_celery() -> ConnectorProbeResult:
    from app.tasks import celery_app

    started = time.perf_counter()
    try:
        def _connect() -> None:
            with celery_app.connection_for_read() as connection:
                connection.ensure_connection(max_retries=0, timeout=2)

        await asyncio.wait_for(asyncio.to_thread(_connect), timeout=3)
    except Exception as exc:
        return _failure("celery", True, started, exc)
    return ConnectorProbeResult(
        name="celery", status=ConnectorState.OK, configured=True,
        latency_ms=_elapsed_ms(started),
    )


async def probe_browser_use() -> ConnectorProbeResult:
    settings = get_settings()
    if not settings.browser_use_api_key:
        return ConnectorProbeResult(
            name="browser_use", status=ConnectorState.DISABLED, configured=False
        )
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(
                "https://api.browser-use.com/api/v2/tasks",
                params={"limit": 1},
                headers={"X-Browser-Use-API-Key": settings.browser_use_api_key},
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        return _failure("browser_use", True, started, exc)
    return ConnectorProbeResult(
        name="browser_use", status=ConnectorState.OK, configured=True,
        latency_ms=_elapsed_ms(started),
    )


async def probe_mailgun() -> ConnectorProbeResult:
    settings = get_settings()
    configured = bool(settings.mailgun_api_key and settings.mailgun_domain)
    if not configured:
        return ConnectorProbeResult(
            name="mailgun", status=ConnectorState.DISABLED, configured=False
        )
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(
                f"{settings.mailgun_api_base_url}/v4/domains/{settings.mailgun_domain}",
                auth=("api", settings.mailgun_api_key),
            )
            response.raise_for_status()
            state = response.json().get("state")
    except (httpx.HTTPError, ValueError) as exc:
        return _failure("mailgun", True, started, exc)
    return ConnectorProbeResult(
        name="mailgun", status=ConnectorState.OK, configured=True,
        latency_ms=_elapsed_ms(started), details={"domain_state": state},
    )


async def probe_configuration_states() -> list[ConnectorProbeResult]:
    settings = get_settings()
    sentry_client = sentry_sdk.get_client()
    return [
        ConnectorProbeResult(
            name="smsapp",
            status=(
                ConnectorState.UNVERIFIED
                if settings.smsapp_api_token
                else ConnectorState.DISABLED
            ),
            configured=bool(settings.smsapp_api_token),
            error_code=("NO_SAFE_READ_PROBE" if settings.smsapp_api_token else None),
        ),
        ConnectorProbeResult(
            name="sentry",
            status=(ConnectorState.OK if sentry_client.transport else ConnectorState.DISABLED),
            configured=bool(sentry_client.transport),
        ),
        ConnectorProbeResult(
            name="camoufox",
            status=(
                ConnectorState.UNVERIFIED
                if settings.camoufox_enabled
                else ConnectorState.DISABLED
            ),
            configured=settings.camoufox_enabled,
        ),
        ConnectorProbeResult(
            name="obscura",
            status=(
                ConnectorState.UNVERIFIED
                if settings.obscura_enabled
                else ConnectorState.DISABLED
            ),
            configured=settings.obscura_enabled,
        ),
    ]


async def collect_connector_probes() -> list[ConnectorProbeResult]:
    live = await asyncio.gather(
        probe_database(), probe_redis(), probe_celery(), probe_smstools(),
        probe_iproxy(), probe_mailgun(), probe_browser_use(),
    )
    return [*live, *(await probe_configuration_states())]


async def probe_connector(name: str) -> ConnectorProbeResult:
    live_probes = {
        "database": probe_database,
        "redis": probe_redis,
        "celery": probe_celery,
        "smstools": probe_smstools,
        "iproxy": probe_iproxy,
        "mailgun": probe_mailgun,
        "browser_use": probe_browser_use,
    }
    if name in live_probes:
        return await live_probes[name]()
    configured = {item.name: item for item in await probe_configuration_states()}
    if name in configured:
        return configured[name]
    raise ValueError(f"Unsupported connector: {name}")


async def refresh_connector_statuses() -> list[ConnectorProbeResult]:
    results = await collect_connector_probes()
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
