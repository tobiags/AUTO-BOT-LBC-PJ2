import time

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.config import get_settings
from app.models import AdminHealthResponse, HealthResponse
from app.services.integration_health import check_database, check_redis, collect_admin_health

router = APIRouter()


def _require_admin_token(x_admin_health_token: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.admin_health_token:
        return
    if x_admin_health_token != settings.admin_health_token:
        raise HTTPException(status_code=401, detail="Invalid admin health token")


@router.get("/health", response_model=HealthResponse, tags=["ops"])
async def health_check() -> HealthResponse:
    """
    Verification minimale pour probes liveness/readiness.
    Retourne toujours HTTP 200; le client lit le champ status.
    """
    db_check = await check_database()
    redis_check = await check_redis(get_settings())

    return HealthResponse(
        status="ok" if (db_check.status == "ok" and redis_check.status == "ok") else "degraded",
        db=db_check.status == "ok",
        redis=redis_check.status == "ok",
        ts=int(time.time()),
    )


@router.get("/api/v1/admin/health", response_model=AdminHealthResponse, tags=["ops"])
async def admin_health_check(
    include_external: bool = Query(default=False),
    _: None = Depends(_require_admin_token),
) -> AdminHealthResponse:
    return await collect_admin_health(include_external=include_external)
