"""
FastAPI app — AutoTransfert SAS P2 (Acquisition Véhicules).
"""
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api import accounts, campaigns, health, listings
from app.config import get_settings
from app.db import Base, engine
from app.webhooks import call, email, sms
from app.ws import ws_manager

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — création des tables si elles n'existent pas
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown
    await engine.dispose()


if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.env, traces_sample_rate=0.1)

app = FastAPI(
    title="AutoTransfert P2 — Acquisition Véhicules",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.env == "development" else [],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(health.router)
app.include_router(accounts.router)
app.include_router(campaigns.router)
app.include_router(listings.router)
app.include_router(sms.router)
app.include_router(email.router)
app.include_router(call.router)


# WebSocket — back-office temps réel
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
