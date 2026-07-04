import logging
import time
from pathlib import Path

import httpx
import redis.asyncio as aioredis
from sqlalchemy import text

from app.config import Settings, get_settings
from app.db import engine
from app.models import AdminHealthResponse, HealthCheckComponent

log = logging.getLogger(__name__)
_APP_NAME = "AutoTransfert P2"
_APP_VERSION = "0.1.0"


def _required_in_env(settings: Settings, component: str) -> bool:
    if component == "browser_use":
        return False
    if component == "sentry":
        return settings.is_production_like()
    return settings.is_production_like()


def _integration_component(
    *,
    name: str,
    configured: bool,
    required: bool,
    details: dict | None = None,
    error: str | None = None,
) -> HealthCheckComponent:
    status = "ok" if configured else ("misconfigured" if required else "disabled")
    if error:
        status = "misconfigured"
    return HealthCheckComponent(
        name=name,
        status=status,
        required=required,
        configured=configured,
        details=details or {},
        error=error,
    )


async def check_database() -> HealthCheckComponent:
    started = time.perf_counter()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        latency_ms = int((time.perf_counter() - started) * 1000)
        return HealthCheckComponent(
            name="database",
            status="ok",
            required=True,
            configured=True,
            latency_ms=latency_ms,
            details={"driver": "sqlalchemy"},
        )
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        log.warning("Database health check failed: %s", exc)
        return HealthCheckComponent(
            name="database",
            status="down",
            required=True,
            configured=True,
            latency_ms=latency_ms,
            error=str(exc),
        )


async def check_redis(settings: Settings) -> HealthCheckComponent:
    started = time.perf_counter()
    redis_client = None
    try:
        redis_client = aioredis.from_url(
            settings.redis_url,
            socket_connect_timeout=settings.healthcheck_timeout_seconds,
        )
        await redis_client.ping()
        latency_ms = int((time.perf_counter() - started) * 1000)
        return HealthCheckComponent(
            name="redis",
            status="ok",
            required=True,
            configured=True,
            latency_ms=latency_ms,
        )
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        log.warning("Redis health check failed: %s", exc)
        return HealthCheckComponent(
            name="redis",
            status="down",
            required=True,
            configured=bool(settings.redis_url),
            latency_ms=latency_ms,
            error=str(exc),
        )
    finally:
        if redis_client is not None:
            await redis_client.aclose()


def check_configuration(settings: Settings) -> list[HealthCheckComponent]:
    checks = [
        _integration_component(
            name="app_secret",
            configured=settings.secret_key not in {"change-me", "change-me-in-production"},
            required=settings.is_production_like(),
            details={"env": settings.env},
        ),
        _integration_component(
            name="sentry",
            configured=bool(settings.sentry_dsn),
            required=_required_in_env(settings, "sentry"),
        ),
        _integration_component(
            name="smstools",
            configured=bool(settings.smstools_api_key and settings.smstools_webhook_secret),
            required=_required_in_env(settings, "smstools"),
        ),
        _integration_component(
            name="iproxy",
            configured=bool(settings.iproxy_api_key and settings.iproxy_proxy_id),
            required=_required_in_env(settings, "iproxy"),
        ),
        _integration_component(
            name="smsapp",
            configured=bool(settings.smsapp_api_token),
            required=_required_in_env(settings, "smsapp"),
        ),
        _integration_component(
            name="mailgun",
            configured=bool(
                settings.mailgun_api_key
                and settings.mailgun_domain
                and settings.mailgun_webhook_signing_key
                and settings.operational_domain
            ),
            required=_required_in_env(settings, "mailgun"),
        ),
        _integration_component(
            name="browser_use",
            configured=bool(settings.browser_use_api_key),
            required=False,
        ),
    ]

    sessions_dir = Path(settings.sessions_dir)
    sessions_dir_is_absolute = settings._is_absolute_path(settings.sessions_dir)
    checks.append(
        HealthCheckComponent(
            name="patchright_storage",
            status="ok" if sessions_dir_is_absolute else "misconfigured",
            required=True,
            configured=sessions_dir_is_absolute,
            details={
                "path": str(sessions_dir),
                "exists": sessions_dir.exists(),
            },
            error=None if sessions_dir_is_absolute else "sessions_dir must be absolute",
        )
    )
    return checks


async def _probe_smstools(settings: Settings, client: httpx.AsyncClient) -> HealthCheckComponent:
    started = time.perf_counter()
    try:
        resp = await client.get(
            "https://api.smstools.org/v1/sims",
            headers={"Authorization": f"Bearer {settings.smstools_api_key}"},
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        if resp.status_code == 401:
            return HealthCheckComponent(
                name="smstools_api",
                status="down",
                required=settings.is_production_like(),
                configured=True,
                latency_ms=latency_ms,
                error="Unauthorized",
            )
        resp.raise_for_status()
        data = resp.json()
        return HealthCheckComponent(
            name="smstools_api",
            status="ok",
            required=settings.is_production_like(),
            configured=True,
            latency_ms=latency_ms,
            details={"sim_count": len(data.get("sims", []))},
        )
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return HealthCheckComponent(
            name="smstools_api",
            status="down",
            required=settings.is_production_like(),
            configured=True,
            latency_ms=latency_ms,
            error=str(exc),
        )


async def _probe_iproxy(settings: Settings, client: httpx.AsyncClient) -> HealthCheckComponent:
    started = time.perf_counter()
    try:
        resp = await client.get(
            "https://iproxy.online/api/cn/v1/proxy-access",
            headers={"Authorization": f"Bearer {settings.iproxy_api_key}"},
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        if resp.status_code == 401:
            return HealthCheckComponent(
                name="iproxy_api",
                status="down",
                required=settings.is_production_like(),
                configured=True,
                latency_ms=latency_ms,
                error="Unauthorized",
            )
        resp.raise_for_status()
        accesses = resp.json().get("proxy_accesses", [])
        proxy_found = any(item.get("id") == settings.iproxy_proxy_id for item in accesses)
        return HealthCheckComponent(
            name="iproxy_api",
            status="ok" if proxy_found else "degraded",
            required=settings.is_production_like(),
            configured=True,
            latency_ms=latency_ms,
            details={"proxy_access_count": len(accesses), "proxy_found": proxy_found},
            error=None if proxy_found else "Configured proxy id not found",
        )
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return HealthCheckComponent(
            name="iproxy_api",
            status="down",
            required=settings.is_production_like(),
            configured=True,
            latency_ms=latency_ms,
            error=str(exc),
        )


async def _probe_browser_use(
    settings: Settings,
    client: httpx.AsyncClient,
) -> HealthCheckComponent:
    started = time.perf_counter()
    try:
        resp = await client.get(
            "https://api.browser-use.com/api/v2/billing/account",
            headers={"X-Browser-Use-API-Key": settings.browser_use_api_key},
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        if resp.status_code == 401:
            return HealthCheckComponent(
                name="browser_use_api",
                status="down",
                required=False,
                configured=True,
                latency_ms=latency_ms,
                error="Unauthorized",
            )
        resp.raise_for_status()
        data = resp.json()
        return HealthCheckComponent(
            name="browser_use_api",
            status="ok",
            required=False,
            configured=True,
            latency_ms=latency_ms,
            details={
                "credits_usd": data.get("totalCreditsBalanceUsd"),
            },
        )
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return HealthCheckComponent(
            name="browser_use_api",
            status="down",
            required=False,
            configured=True,
            latency_ms=latency_ms,
            error=str(exc),
        )


async def check_external_integrations(settings: Settings) -> list[HealthCheckComponent]:
    async with httpx.AsyncClient(timeout=settings.healthcheck_timeout_seconds) as client:
        checks: list[HealthCheckComponent] = []
        if settings.smstools_api_key and settings.smstools_webhook_secret:
            checks.append(await _probe_smstools(settings, client))
        if settings.iproxy_api_key and settings.iproxy_proxy_id:
            checks.append(await _probe_iproxy(settings, client))
        if settings.browser_use_api_key:
            checks.append(await _probe_browser_use(settings, client))
        return checks


def _build_summary(checks: list[HealthCheckComponent]) -> dict[str, int]:
    summary = {"ok": 0, "degraded": 0, "down": 0, "disabled": 0, "misconfigured": 0}
    for check in checks:
        summary[check.status] = summary.get(check.status, 0) + 1
    return summary


def _overall_status(checks: list[HealthCheckComponent]) -> str:
    for check in checks:
        if check.required and check.status in {"down", "degraded", "misconfigured"}:
            return "degraded"
    if any(check.status in {"down", "degraded", "misconfigured"} for check in checks):
        return "degraded"
    return "ok"


async def collect_admin_health(
    *,
    include_external: bool = False,
    settings: Settings | None = None,
) -> AdminHealthResponse:
    settings = settings or get_settings()
    checks = [await check_database(), await check_redis(settings), *check_configuration(settings)]
    if include_external:
        checks.extend(await check_external_integrations(settings))

    return AdminHealthResponse(
        status=_overall_status(checks),
        env=settings.env,
        app=_APP_NAME,
        version=_APP_VERSION,
        ts=int(time.time()),
        external_checks=include_external,
        checks=checks,
        summary=_build_summary(checks),
    )
