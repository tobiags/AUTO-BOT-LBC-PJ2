import time

import redis.asyncio as aioredis
from fastapi import APIRouter
from sqlalchemy import text

from app.config import get_settings
from app.db import engine
from app.models import HealthResponse

router = APIRouter()
settings = get_settings()


@router.get("/health", response_model=HealthResponse, tags=["ops"])
async def health_check():
    """
    Vérifie la connectivité DB + Redis.
    Retourne status="ok" si tout est up, "degraded" sinon.
    Toujours HTTP 200 — le client lit le champ status.
    """
    db_ok = False
    redis_ok = False

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    try:
        r = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        redis_ok = True
    except Exception:
        pass

    return HealthResponse(
        status="ok" if (db_ok and redis_ok) else "degraded",
        db=db_ok,
        redis=redis_ok,
        ts=int(time.time()),
    )
