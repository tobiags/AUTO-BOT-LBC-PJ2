"""Tests GET /health."""
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_health_ok(client):
    with (
        patch("app.api.health.engine") as mock_engine,
        patch("app.api.health.aioredis.from_url") as mock_redis_factory,
    ):
        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_conn.execute = AsyncMock()
        mock_engine.connect.return_value = mock_conn

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()
        mock_redis.aclose = AsyncMock()
        mock_redis_factory.return_value = mock_redis

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
        patch("app.api.health.engine") as mock_engine,
        patch("app.api.health.aioredis.from_url") as mock_redis_factory,
    ):
        mock_engine.connect.side_effect = Exception("DB down")

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()
        mock_redis.aclose = AsyncMock()
        mock_redis_factory.return_value = mock_redis

        resp = await client.get("/health")
        # Toujours HTTP 200 même si dégradé
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["db"] is False
        assert data["redis"] is True
