"""Tests GET /health and /api/v1/admin/health."""
from unittest.mock import AsyncMock, patch

import pytest

from app.config import Settings
from app.models import AdminHealthResponse, HealthCheckComponent


@pytest.mark.asyncio
async def test_health_ok(client):
    with (
        patch("app.api.health.check_database", new_callable=AsyncMock) as mock_db,
        patch("app.api.health.check_redis", new_callable=AsyncMock) as mock_redis,
    ):
        mock_db.return_value = HealthCheckComponent(
            name="database",
            status="ok",
            required=True,
            configured=True,
        )
        mock_redis.return_value = HealthCheckComponent(
            name="redis",
            status="ok",
            required=True,
            configured=True,
        )

        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["db"] is True
        assert data["redis"] is True
        assert "ts" in data


@pytest.mark.asyncio
async def test_health_degraded_no_db(client):
    with (
        patch("app.api.health.check_database", new_callable=AsyncMock) as mock_db,
        patch("app.api.health.check_redis", new_callable=AsyncMock) as mock_redis,
    ):
        mock_db.return_value = HealthCheckComponent(
            name="database",
            status="down",
            required=True,
            configured=True,
            error="DB down",
        )
        mock_redis.return_value = HealthCheckComponent(
            name="redis",
            status="ok",
            required=True,
            configured=True,
        )

        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["db"] is False
        assert data["redis"] is True


@pytest.mark.asyncio
async def test_admin_health_includes_component_details(client):
    report = AdminHealthResponse(
        status="degraded",
        env="development",
        app="AutoTransfert P2",
        version="0.1.0",
        ts=123456,
        external_checks=False,
        checks=[
            HealthCheckComponent(
                name="database",
                status="ok",
                required=True,
                configured=True,
                latency_ms=12,
            ),
            HealthCheckComponent(
                name="smstools",
                status="disabled",
                required=False,
                configured=False,
            ),
        ],
        summary={"ok": 1, "degraded": 0, "down": 0, "disabled": 1, "misconfigured": 0},
    )
    with patch("app.api.health.collect_admin_health", new_callable=AsyncMock) as collect:
        collect.return_value = report
        resp = await client.get("/api/v1/admin/health")

    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_admin_health_requires_token_when_configured(client):
    settings = Settings(
        env="development",
        secret_key="local-secret",
        admin_health_token="health-token",
    )
    report = AdminHealthResponse(
        status="ok",
        env="development",
        app="AutoTransfert P2",
        version="0.1.0",
        ts=123456,
        external_checks=False,
        checks=[],
        summary={"ok": 0, "degraded": 0, "down": 0, "disabled": 0, "misconfigured": 0},
    )
    with (
        patch("app.api.health.get_settings", return_value=settings),
        patch("app.api.health.collect_admin_health", new_callable=AsyncMock) as collect,
    ):
        collect.return_value = report
        resp = await client.get("/api/v1/admin/health")
        assert resp.status_code == 401

        ok_resp = await client.get(
            "/api/v1/admin/health",
            headers={"x-admin-health-token": "health-token"},
        )
        assert ok_resp.status_code == 200
