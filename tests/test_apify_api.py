from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.api.apify import _redact_phones
from app.security import require_control_role


def test_control_roles_enforce_minimum_and_support_french_aliases():
    require_control_role("administrateur", "admin")
    require_control_role("manager", "operator")
    with pytest.raises(HTTPException) as error:
        require_control_role("viewer", "admin")
    assert error.value.status_code == 403


async def test_viewer_cannot_add_apify_account(client):
    response = await client.post(
        "/api/v1/apify/accounts",
        json={"label": "Principal", "token": "apify_api_secret"},
        headers={"X-Operator-Role": "viewer"},
    )

    assert response.status_code == 403


def test_nested_raw_phone_is_redacted_for_viewers():
    payload = {
        "seller": {"description": "Appelez-moi au 06 12 34 56 78"},
        "rows": [{"mobile": "+33612345678"}],
    }

    redacted = _redact_phones(payload)

    assert "0612345678" not in str(redacted).replace(" ", "")
    assert "+33612345678" not in str(redacted).replace(" ", "")
    assert redacted["rows"][0]["mobile"] == "+33 ** ** ** 67 8"


@pytest.mark.integration
@patch("app.boundaries.apify_validate_token", new_callable=AsyncMock)
async def test_account_response_never_contains_token(validate_token, client):
    validate_token.return_value = {"id": "user-1", "username": "owner"}
    response = await client.post(
        "/api/v1/apify/accounts",
        json={"label": "Principal", "token": "apify_api_secret"},
        headers={"X-Operator-Role": "admin"},
    )

    body = response.text
    assert response.status_code == 201
    assert "apify_api_secret" not in body
    assert "ciphertext" not in body
