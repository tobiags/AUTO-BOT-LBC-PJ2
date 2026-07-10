from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.models import ConnectorState


@pytest.mark.asyncio
async def test_probe_iproxy_does_not_retry_authentication_failure():
    from app.services.connector_monitor import probe_iproxy

    request = httpx.Request("GET", "https://iproxy.online")
    response = httpx.Response(401, request=request)
    error = httpx.HTTPStatusError("unauthorized", request=request, response=response)
    settings = SimpleNamespace(
        iproxy_api_key="api-key",
        iproxy_connection_id="connection-1",
        iproxy_proxy_id="proxy-1",
    )

    with (
        patch("app.services.connector_monitor.get_settings", return_value=settings),
        patch(
            "app.services.connector_monitor.boundaries.get_4g_proxy",
            new_callable=AsyncMock,
        ) as probe,
    ):
        probe.side_effect = error
        result = await probe_iproxy()

    assert result.status == ConnectorState.MISCONFIGURED
    assert result.error_code == "HTTP_401"
    assert result.configured is True
    probe.assert_awaited_once()


@pytest.mark.asyncio
async def test_probe_smstools_reports_success_latency():
    from app.services.connector_monitor import probe_smstools

    settings = SimpleNamespace(smstools_api_key="api-key")
    with (
        patch("app.services.connector_monitor.get_settings", return_value=settings),
        patch(
            "app.services.connector_monitor.boundaries.get_sim_list",
            new_callable=AsyncMock,
            return_value=[{"id": "sim-1", "status": "active"}],
        ),
    ):
        result = await probe_smstools()

    assert result.status == ConnectorState.OK
    assert result.configured is True
    assert result.details == {"active_sims": 1}
    assert result.latency_ms is not None
    assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_refresh_connector_statuses_persists_each_probe():
    from app.models import ConnectorProbeResult
    from app.services.connector_monitor import refresh_connector_statuses

    class _Context:
        async def __aenter__(self):
            return db

        async def __aexit__(self, exc_type, exc, tb):
            return False

    db = AsyncMock()
    smstools = ConnectorProbeResult(
        name="smstools",
        status=ConnectorState.OK,
        configured=True,
    )
    iproxy = ConnectorProbeResult(
        name="iproxy",
        status=ConnectorState.MISCONFIGURED,
        configured=True,
        error_code="HTTP_401",
    )

    with (
        patch(
            "app.services.connector_monitor.probe_smstools",
            new_callable=AsyncMock,
            return_value=smstools,
        ),
        patch(
            "app.services.connector_monitor.probe_iproxy",
            new_callable=AsyncMock,
            return_value=iproxy,
        ),
        patch("app.services.connector_monitor.get_db", return_value=_Context()),
    ):
        results = await refresh_connector_statuses()

    assert results == [smstools, iproxy]
    assert db.execute.await_count == 2
