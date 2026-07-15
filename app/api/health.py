import secrets
import time
from collections import Counter
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import text

from app.config import Settings, get_settings
from app.db import engine
from app.models import AdminHealthResponse, HealthCheckComponent, HealthResponse

router = APIRouter()


async def check_database() -> HealthCheckComponent:
    started = time.perf_counter()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        return HealthCheckComponent(
            name="database",
            status="down",
            required=True,
            configured=True,
            latency_ms=_elapsed_ms(started),
            error=str(exc),
        )

    return HealthCheckComponent(
        name="database",
        status="ok",
        required=True,
        configured=True,
        latency_ms=_elapsed_ms(started),
    )


async def check_redis() -> HealthCheckComponent:
    settings = get_settings()
    started = time.perf_counter()
    redis_client = None
    try:
        redis_client = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
        await redis_client.ping()
    except Exception as exc:
        return HealthCheckComponent(
            name="redis",
            status="down",
            required=True,
            configured=bool(settings.redis_url),
            latency_ms=_elapsed_ms(started),
            error=str(exc),
        )
    finally:
        if redis_client is not None:
            await redis_client.aclose()

    return HealthCheckComponent(
        name="redis",
        status="ok",
        required=True,
        configured=True,
        latency_ms=_elapsed_ms(started),
    )


async def collect_admin_health(external_checks: bool = False) -> AdminHealthResponse:
    settings = get_settings()
    checks = [await check_database(), await check_redis()]

    if external_checks:
        checks.extend(_external_configuration_checks(settings))

    summary = _summarize_checks(checks)
    status = "ok" if all(check.status == "ok" for check in checks if check.required) else "degraded"

    return AdminHealthResponse(
        status=status,
        env=settings.env,
        app="AutoTransfert P2",
        version="0.1.0",
        ts=int(time.time()),
        external_checks=external_checks,
        checks=checks,
        summary=summary,
    )


@router.get("/health", response_model=HealthResponse, tags=["ops"])
async def health_check():
    db_check = await check_database()
    redis_check = await check_redis()

    db_ok = db_check.status == "ok"
    redis_ok = redis_check.status == "ok"

    return HealthResponse(
        status="ok" if (db_ok and redis_ok) else "degraded",
        db=db_ok,
        redis=redis_ok,
        ts=int(time.time()),
    )


@router.get("/api/v1/admin/health", response_model=AdminHealthResponse, tags=["ops"])
async def admin_health(
    x_admin_health_token: Annotated[str | None, Header()] = None,
    external_checks: bool = False,
):
    settings = get_settings()
    if not settings.admin_health_token:
        raise HTTPException(status_code=503, detail="Admin health token is not configured")
    if not _token_matches(
        x_admin_health_token,
        settings.admin_health_token,
    ):
        raise HTTPException(status_code=401, detail="Invalid admin health token")

    return await collect_admin_health(external_checks=external_checks)


def _elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def _token_matches(provided: str | None, expected: str) -> bool:
    return provided is not None and secrets.compare_digest(provided, expected)


def _summarize_checks(checks: list[HealthCheckComponent]) -> dict[str, int]:
    statuses = ["ok", "degraded", "down", "disabled", "misconfigured"]
    counts = Counter(check.status for check in checks)
    return {status: counts.get(status, 0) for status in statuses}


def _external_configuration_checks(settings: Settings) -> list[HealthCheckComponent]:
    optional_services = {
        "smstools": settings.smstools_api_key,
        "iproxy": settings.iproxy_api_key,
        "smsapp": settings.smsapp_api_token,
        "mailgun": settings.mailgun_api_key and settings.mailgun_domain,
        "sentry": settings.sentry_dsn,
        "browser_use": settings.browser_use_api_key,
    }
    return [
        HealthCheckComponent(
            name=name,
            status="ok" if configured else "disabled",
            required=False,
            configured=bool(configured),
        )
        for name, configured in optional_services.items()
    ]
