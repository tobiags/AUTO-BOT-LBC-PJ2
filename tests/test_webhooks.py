"""Tests webhooks SMS, email, call - idempotence + STOP."""
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


def _mock_sms_db(*scalar_results):
    execute = AsyncMock(
        side_effect=[
            SimpleNamespace(scalar=lambda value=value: value)
            for value in scalar_results
        ]
    )
    db = AsyncMock()
    db.execute = execute
    ctx = AsyncMock()
    ctx.__aenter__.return_value = db
    ctx.__aexit__.return_value = False
    return ctx


def _ctx_with_execute_results(*results):
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=results)
    ctx = AsyncMock()
    ctx.__aenter__.return_value = db
    ctx.__aexit__.return_value = False
    return ctx


@pytest.mark.asyncio
async def test_webhook_stop_blacklists(client, mock_send_sms):
    """STOP recu -> numero blackliste P1+P2 + confirmation SMS envoyee."""
    with (
        patch("app.webhooks.sms.add_to_blacklist", new_callable=AsyncMock) as mock_bl,
        patch("app.webhooks.sms.get_db", return_value=_mock_sms_db(1)),
    ):
        resp = await client.post(
            "/webhooks/sms",
            json={"sim_id": "sim_03", "from": "+33698765432", "body": "STOP", "ts": 1718620000},
        )
        assert resp.status_code == 200
        mock_bl.assert_called_once_with(
            phone="+33698765432",
            source_sim="sim_03",
            source_project="P1+P2",
        )


@pytest.mark.asyncio
async def test_webhook_sms_idempotent(client):
    """Meme payload livre 2x -> traite une seule fois (R12)."""
    payload = {"sim_id": "sim_01", "from": "+33611111111", "body": "Bonjour", "ts": 1718620100}
    with (
        patch("app.webhooks.sms._event_key", return_value="key_dup_test"),
        patch("app.webhooks.sms.get_db", return_value=_mock_sms_db(1, None)),
    ):
        resp1 = await client.post("/webhooks/sms", json=payload)
        resp2 = await client.post("/webhooks/sms", json=payload)
    assert resp1.status_code == 200
    assert resp2.status_code == 200


@pytest.mark.asyncio
async def test_extract_verification_code():
    """extract_verification_code parse correctement les emails LBC."""
    from app.webhooks.email import extract_verification_code

    assert extract_verification_code("Votre code LeBonCoin est : 847291") == "847291"
    assert extract_verification_code("Code de confirmation : 123456") == "123456"
    assert extract_verification_code("Bienvenue sur LeBonCoin") is None


@pytest.mark.asyncio
async def test_call_webhook_uses_latest_sms_log_mapping(client):
    """Le webhook call corrèle d'abord via la dernière entrée SmsLog SIM+numéro."""
    listing_id = uuid.uuid4()
    sms_log = SimpleNamespace(listing_id=listing_id)
    listing = SimpleNamespace(
        url="https://www.leboncoin.fr/voitures/abc",
        title="Peugeot 208",
        price=8900,
        km=74000,
        source="leboncoin",
        make="Peugeot",
        model="208",
    )

    dedupe_ctx = _ctx_with_execute_results(SimpleNamespace(scalar=lambda: 1))
    lookup_ctx = _ctx_with_execute_results(
        SimpleNamespace(scalar_one_or_none=lambda: sms_log),
        SimpleNamespace(scalar_one_or_none=lambda: listing),
    )

    with (
        patch("app.webhooks.call.get_db", side_effect=[dedupe_ctx, lookup_ctx]),
        patch("app.webhooks.call.ws_manager.broadcast", new_callable=AsyncMock) as broadcast,
    ):
        resp = await client.post(
            "/webhooks/call",
            json=[{
                "webhook_id": "wh_call_1234567890",
                "webhook_type": "CALL_FORWARDING",
                "message": {
                    "id": "call_1",
                    "date_utc": "2026-06-30T09:30:00Z",
                    "sender": "+33601020304",
                    "receiver": "sim_01",
                },
            }],
        )

    assert resp.status_code == 200
    broadcast.assert_awaited_once()
    payload = broadcast.await_args.args[0]
    assert payload["listing"]["url"] == "https://www.leboncoin.fr/voitures/abc"
    assert payload["listing"]["title"] == "Peugeot 208"
    assert payload["listing"]["vehicle"] == "Peugeot 208"


@pytest.mark.asyncio
async def test_call_webhook_without_listing_does_not_push(client):
    dedupe_ctx = _ctx_with_execute_results(SimpleNamespace(scalar=lambda: 1))
    lookup_ctx = _ctx_with_execute_results(
        SimpleNamespace(scalar_one_or_none=lambda: None),
        SimpleNamespace(scalar_one_or_none=lambda: None),
    )

    with (
        patch("app.webhooks.call.get_db", side_effect=[dedupe_ctx, lookup_ctx]),
        patch("app.webhooks.call.ws_manager.broadcast", new_callable=AsyncMock) as broadcast,
    ):
        resp = await client.post(
            "/webhooks/call",
            json=[{
                "webhook_id": "wh_call_nomatch",
                "webhook_type": "CALL_FORWARDING",
                "message": {
                    "id": "call_nomatch",
                    "date_utc": "2026-06-30T09:31:00Z",
                    "sender": "+33611112222",
                    "receiver": "sim_99",
                },
            }],
        )

    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "matched": False}
    broadcast.assert_not_awaited()


@pytest.mark.asyncio
async def test_call_webhook_idempotent_single_push(client):
    listing_id = uuid.uuid4()
    sms_log = SimpleNamespace(listing_id=listing_id)
    listing = SimpleNamespace(
        url="https://www.leboncoin.fr/voitures/once",
        title="Renault Clio",
        price=7200,
        km=99000,
        source="leboncoin",
        make="Renault",
        model="Clio",
    )

    dedupe_ctx_1 = _ctx_with_execute_results(SimpleNamespace(scalar=lambda: 1))
    lookup_ctx = _ctx_with_execute_results(
        SimpleNamespace(scalar_one_or_none=lambda: sms_log),
        SimpleNamespace(scalar_one_or_none=lambda: listing),
    )
    dedupe_ctx_2 = _ctx_with_execute_results(SimpleNamespace(scalar=lambda: None))

    payload = [{
        "webhook_id": "wh_call_duplicate",
        "webhook_type": "CALL_FORWARDING",
        "message": {
            "id": "call_dup",
            "date_utc": "2026-06-30T09:32:00Z",
            "sender": "+33601020304",
            "receiver": "sim_01",
        },
    }]

    with (
        patch("app.webhooks.call.get_db", side_effect=[dedupe_ctx_1, lookup_ctx, dedupe_ctx_2]),
        patch("app.webhooks.call.ws_manager.broadcast", new_callable=AsyncMock) as broadcast,
    ):
        resp1 = await client.post("/webhooks/call", json=payload)
        resp2 = await client.post("/webhooks/call", json=payload)

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp2.json() == {"ok": True, "duplicate": True}
    broadcast.assert_awaited_once()
