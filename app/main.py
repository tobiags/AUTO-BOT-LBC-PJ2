"""
FastAPI app - AutoTransfert SAS P2 (Acquisition Vehicules).
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import sentry_sdk
from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    accounts,
    analyzer,
    campaigns,
    contacts,
    dashboard,
    email_inbox,
    email_identities,
    health,
    listings,
    operations,
    workspace,
)
from app.config import get_settings
from app.db import engine
from app.security import require_control_token, require_webhook_secret, websocket_token_is_valid
from app.services.balance_poller import start_balance_poller
from app.webhooks import call, email, funds, sms
from app.ws import ws_manager

settings = get_settings()
log = logging.getLogger(__name__)


def validate_startup_or_raise() -> None:
    Path(settings.sessions_dir).mkdir(parents=True, exist_ok=True)
    if settings.is_production_like() and not settings.admin_health_token:
        log.warning("admin_health_token is not configured; admin health endpoint is unprotected")


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_startup_or_raise()
    poller_task = asyncio.create_task(start_balance_poller())
    try:
        yield
    finally:
        poller_task.cancel()
        await engine.dispose()


if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.env, traces_sample_rate=0.1)

app = FastAPI(
    title="AutoTransfert P2 - Acquisition Vehicules",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.env == "development" else [],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
protected = [Depends(require_control_token)]
app.include_router(accounts.router, dependencies=protected)
app.include_router(campaigns.router, dependencies=protected)
app.include_router(listings.router, dependencies=protected)
app.include_router(analyzer.router, dependencies=protected)
app.include_router(sms.router, dependencies=[Depends(require_webhook_secret)])
app.include_router(email.router)
app.include_router(call.router, dependencies=[Depends(require_webhook_secret)])
app.include_router(funds.router, dependencies=[Depends(require_webhook_secret)])
app.include_router(dashboard.router, dependencies=protected)
app.include_router(operations.router)
app.include_router(email_identities.router, dependencies=protected)
app.include_router(email_inbox.router, dependencies=protected)
app.include_router(workspace.router, dependencies=protected)
app.include_router(contacts.router, dependencies=protected)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str | None = None):
    if not websocket_token_is_valid(token):
        await websocket.close(code=4401)
        return
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
