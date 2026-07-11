from unittest.mock import AsyncMock, patch

import httpx
import pytest


@pytest.mark.asyncio
async def test_browser_use_client_creates_and_polls_task():
    from app.services.browser_use_cloud import BrowserUseCloudClient

    responses = [
        httpx.Response(201, json={"id": "task-1", "sessionId": "session-1"}),
        httpx.Response(200, json={"status": "finished", "output": "ok", "cost": 0.12}),
        httpx.Response(200, json={
            "id": "task-1",
            "sessionId": "session-1",
            "status": "finished",
            "isSuccess": True,
            "output": "ok",
            "outputFiles": [{"name": "report.json", "url": "https://files.test/report"}],
            "steps": [],
        }),
    ]
    request = AsyncMock(side_effect=responses)

    with patch("httpx.AsyncClient.request", request):
        client = BrowserUseCloudClient(api_key="bu_test")
        task = await client.create_task(
            task="Inspecte la page",
            metadata={"template": "diagnostic"},
        )
        status = await client.get_task_status(task["id"])
        detail = await client.get_task(task["id"])

    assert task["id"] == "task-1"
    assert status["cost"] == 0.12
    assert detail["outputFiles"][0]["name"] == "report.json"
    assert request.await_count == 3


@pytest.mark.asyncio
async def test_browser_use_client_stops_task_and_session():
    from app.services.browser_use_cloud import BrowserUseCloudClient

    with patch(
        "httpx.AsyncClient.request",
        new_callable=AsyncMock,
        return_value=httpx.Response(200, json={"id": "task-1", "status": "stopped"}),
    ) as request:
        client = BrowserUseCloudClient(api_key="bu_test")
        result = await client.stop_task("task-1", stop_session=True)

    assert result["status"] == "stopped"
    assert request.await_args.kwargs["json"] == {"action": "stop_task_and_session"}


def test_browser_use_templates_are_domain_bounded():
    from app.services.browser_use_cloud import BROWSER_USE_TEMPLATES

    assert set(BROWSER_USE_TEMPLATES) >= {
        "listing_diagnostic",
        "listing_enrichment",
        "messaging_assist",
        "account_diagnostic",
    }
    assert all(template.allowed_domains for template in BROWSER_USE_TEMPLATES.values())
