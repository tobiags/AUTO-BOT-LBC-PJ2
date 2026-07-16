from unittest.mock import patch

import pytest


@pytest.mark.integration
async def test_duplicate_apify_webhook_dispatches_one_import(
    client, existing_apify_account, configured_apify_binding
):
    payload = {
        "eventType": "ACTOR.RUN.SUCCEEDED",
        "resource": {
            "id": "run-123",
            "status": "SUCCEEDED",
            "defaultDatasetId": "ds-1",
        },
    }
    headers = {"Authorization": "Bearer test-apify-webhook-secret"}

    with patch("app.tasks.import_apify_run_task.delay") as dispatch:
        first = await client.post(
            f"/webhooks/apify/{existing_apify_account.id}",
            json=payload,
            headers=headers,
        )
        second = await client.post(
            f"/webhooks/apify/{existing_apify_account.id}",
            json=payload,
            headers=headers,
        )

    assert configured_apify_binding.account_id == existing_apify_account.id
    assert first.status_code == 202
    assert second.status_code == 202
    dispatch.assert_called_once()
