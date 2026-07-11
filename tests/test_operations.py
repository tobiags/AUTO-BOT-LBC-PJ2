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
