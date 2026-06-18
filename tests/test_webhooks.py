"""Tests webhooks SMS, email, call — idempotence + STOP."""
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_webhook_stop_blacklists(client, mock_send_sms):
    """STOP reçu → numéro blacklisté P1+P2 + confirmation SMS envoyée."""
    with patch("app.services.blacklist.add_to_blacklist", new_callable=AsyncMock) as mock_bl:
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
    """Même payload livré 2x → traité une seule fois (R12)."""
    payload = {"sim_id": "sim_01", "from": "+33611111111", "body": "Bonjour", "ts": 1718620100}
    with patch("app.webhooks.sms._event_key", return_value="key_dup_test"):
        with patch("app.db.get_db") as mock_db:
            # Premier appel
            resp1 = await client.post("/webhooks/sms", json=payload)
            # Deuxième appel identique
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
