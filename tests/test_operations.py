from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_connector_command_requires_control_tower_token(client):
    with patch("app.api.operations.get_settings") as settings:
        settings.return_value.control_tower_token = "secret-token"
        response = await client.post(
            "/api/v1/operations/connectors/iproxy/commands",
            json={"action": "probe", "idempotency_key": "probe-001"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_ip_rotation_requires_admin_confirmation(client):
    with patch("app.api.operations.get_settings") as settings:
        settings.return_value.control_tower_token = "secret-token"
        response = await client.post(
            "/api/v1/operations/connectors/iproxy/commands",
            headers={
                "X-Control-Tower-Token": "secret-token",
                "X-Operator-Role": "operator",
                "X-Operator-Id": "tests",
            },
            json={"action": "rotate_ip", "idempotency_key": "rotate-001"},
        )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ADMIN_CONFIRMATION_REQUIRED"


@pytest.mark.asyncio
async def test_connector_probe_dispatches_typed_command(client):
    with (
        patch("app.api.operations.get_settings") as settings,
        patch(
            "app.api.operations.execute_connector_command",
            new_callable=AsyncMock,
        ) as execute,
    ):
        settings.return_value.control_tower_token = "secret-token"
        execute.return_value = {
            "command_id": "11111111-1111-1111-1111-111111111111",
            "status": "completed",
            "connector": "iproxy",
            "action": "probe",
            "detail": {"status": "ok"},
        }
        response = await client.post(
            "/api/v1/operations/connectors/iproxy/commands",
            headers={
                "X-Control-Tower-Token": "secret-token",
                "X-Operator-Role": "operator",
                "X-Operator-Id": "tests",
            },
            json={"action": "probe", "idempotency_key": "probe-002"},
        )

    assert response.status_code == 200
    execute.assert_awaited_once()
    assert response.json()["detail"] == {"status": "ok"}


@pytest.mark.asyncio
async def test_viewer_can_read_workflow_history(client):
    with (
        patch("app.api.operations.get_settings") as settings,
        patch(
            "app.api.operations.list_workflows",
            new_callable=AsyncMock,
        ) as list_history,
    ):
        settings.return_value.control_tower_token = "secret-token"
        list_history.return_value = []
        response = await client.get(
            "/api/v1/operations/workflows",
            headers={
                "X-Control-Tower-Token": "secret-token",
                "X-Operator-Role": "viewer",
            },
        )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_viewer_cannot_run_connector_command(client):
    with patch("app.api.operations.get_settings") as settings:
        settings.return_value.control_tower_token = "secret-token"
        response = await client.post(
            "/api/v1/operations/connectors/iproxy/commands",
            headers={
                "X-Control-Tower-Token": "secret-token",
                "X-Operator-Role": "viewer",
            },
            json={"action": "probe", "idempotency_key": "probe-viewer"},
        )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "INSUFFICIENT_ROLE"


@pytest.mark.asyncio
async def test_operator_can_create_audited_campaign(client):
    with (
        patch("app.api.operations.get_settings") as settings,
        patch(
            "app.api.operations.create_controlled_campaign",
            new_callable=AsyncMock,
        ) as create_campaign,
    ):
        settings.return_value.control_tower_token = "secret-token"
        create_campaign.return_value = {
            "id": "11111111-1111-1111-1111-111111111111",
            "type": "lbc_message",
            "status": "PENDING",
            "sent": 0,
            "failed": 0,
            "scheduled_at": None,
            "last_error": None,
            "created_at": "2026-07-11T12:00:00Z",
        }
        response = await client.post(
            "/api/v1/operations/campaigns",
            headers={
                "X-Control-Tower-Token": "secret-token",
                "X-Operator-Role": "operator",
                "X-Operator-Id": "tests",
            },
            json={
                "type": "lbc_message",
                "message_template": "Bonjour",
                "quota_per_sim": 15,
                "idempotency_key": "campaign-create-001",
            },
        )

    assert response.status_code == 201
    create_campaign.assert_awaited_once()
