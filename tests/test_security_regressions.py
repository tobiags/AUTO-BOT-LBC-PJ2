import hashlib
import hmac
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api.apify import _redact_phones
from app.main import app
from app.models import ApifyAccountOut, ApifyBindingOut, ApifyItemOut, ApifyRunOut


@pytest.mark.asyncio
async def test_legacy_accounts_requires_control_token(client):
    settings = SimpleNamespace(control_tower_token="control-secret")
    with (
        patch("app.security.get_settings", return_value=settings),
        patch("app.api.accounts.get_db") as get_db,
    ):
        get_db.return_value.__aenter__ = AsyncMock()
        response = await client.get("/accounts", headers={"X-Control-Tower-Token": ""})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_sms_webhook_rejects_missing_shared_secret(client):
    settings = SimpleNamespace(smstools_webhook_secret="webhook-secret")
    with patch("app.security.get_settings", return_value=settings):
        response = await client.post(
            "/webhooks/sms",
            json={"sim_id": "sim_01", "from": "+33611111111", "body": "Bonjour"},
            headers={"X-Webhook-Secret": ""},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_mailgun_rejects_invalid_signature(client):
    response = await client.post(
        "/webhooks/email",
        data={
            "recipient": "account@example.test",
            "sender": "noreply@leboncoin.fr",
            "body-plain": "Votre code est 847291",
            "timestamp": str(int(time.time())),
            "token": "mailgun-token",
            "signature": "invalid",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_mailgun_response_never_exposes_otp(client):
    timestamp = str(int(time.time()))
    token = "mailgun-token"
    key = "mailgun-signing-key"
    signature = hmac.new(key.encode(), f"{timestamp}{token}".encode(), hashlib.sha256).hexdigest()

    settings = SimpleNamespace(mailgun_webhook_signing_key=key)
    with (
        patch("app.security.get_settings", return_value=settings),
        patch("app.webhooks.email.get_db") as get_db,
        patch(
            "app.webhooks.email.store_inbound_message",
            new_callable=AsyncMock,
        ),
    ):
        db = AsyncMock()
        db.execute.side_effect = [
            type("Result", (), {"scalar": lambda self: 1})(),
            type("Result", (), {"scalar_one_or_none": lambda self: None})(),
        ]
        get_db.return_value.__aenter__.return_value = db
        response = await client.post(
            "/webhooks/email",
            data={
                "recipient": "account@example.test",
                "sender": "noreply@leboncoin.fr",
                "body-plain": "Votre code est 847291",
                "timestamp": timestamp,
                "token": token,
                "signature": signature,
            },
        )

    assert response.status_code == 200
    assert "847291" not in response.text
    assert "code" not in response.json()


def test_websocket_rejects_missing_token():
    with pytest.raises(WebSocketDisconnect) as exc:
        with TestClient(app).websocket_connect("/ws"):
            pass
    assert exc.value.code == 4401


def test_apify_public_contracts_never_expose_secret_storage_fields():
    public_fields = set().union(
        ApifyAccountOut.model_fields,
        ApifyBindingOut.model_fields,
        ApifyRunOut.model_fields,
        ApifyItemOut.model_fields,
    )

    assert "token" not in public_fields
    assert "token_ciphertext" not in public_fields
    assert "input_ciphertext" not in public_fields
    assert "webhook_secret_ciphertext" not in public_fields


def test_apify_raw_html_remains_text_and_phone_is_masked():
    payload = {
        "title": '<img src=x onerror="alert(1)">',
        "seller": {"phone": "06 12 34 56 78"},
    }

    redacted = _redact_phones(payload)

    assert redacted["title"] == payload["title"]
    assert redacted["seller"]["phone"] == "+33 ** ** ** 67 8"


@pytest.mark.integration
async def test_forged_apify_webhook_is_rejected_without_secret_echo(
    client,
    existing_apify_account,
):
    response = await client.post(
        f"/webhooks/apify/{existing_apify_account.id}",
        json={
            "eventType": "ACTOR.RUN.SUCCEEDED",
            "resource": {"id": "forged-run", "status": "SUCCEEDED"},
        },
        headers={"Authorization": "Bearer forged-apify-secret"},
    )

    assert response.status_code == 401
    assert "forged-apify-secret" not in response.text
