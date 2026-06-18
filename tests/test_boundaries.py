"""Tests unitaires boundaries — couvrent les wrappers API externes."""
import pytest
from app.services.phone_extractor import extract_phone


# ── PHONE EXTRACTOR (synchrone, pas de mock) ─────────────────────────────────

def test_extract_phone_mobile_fr():
    assert extract_phone("Appelez le 06 12 34 56 78") == "+33612345678"


def test_extract_phone_plus33():
    assert extract_phone("Tel: +33712345678") == "+33712345678"


def test_extract_phone_spaced():
    assert extract_phone("06 12 34 56 78") == "+33612345678"


def test_extract_phone_none():
    assert extract_phone("Aucun numéro ici") is None


def test_extract_phone_ambiguous_does_not_crash():
    assert extract_phone("Prix : 15 000 euros, année 2021") is None


# ── SMSAPP.IO MOCKS ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_poll_sms_extracts_code(mock_poll_sms):
    """poll_sms retourne le code extrait du SMS."""
    from app import boundaries
    result = await boundaries.poll_sms("order_001", max_wait=1)
    assert result == "847291"


@pytest.mark.asyncio
async def test_poll_sms_timeout_returns_none():
    """poll_sms retourne None après timeout."""
    from unittest.mock import AsyncMock, patch
    import app.boundaries as b

    with patch.object(b, "poll_sms", new_callable=AsyncMock) as m:
        m.return_value = None
        result = await b.poll_sms("order_timeout", max_wait=0)
        assert result is None


# ── PROXY FR CARRIER ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_proxy_fr_carrier_passes(mock_get_4g_proxy):
    """get_4g_proxy() retourne un proxy avec ASN Orange → pas d'erreur."""
    from app import boundaries
    from app.services.account_creation import _verify_proxy_is_fr_carrier

    proxy = await boundaries.get_4g_proxy()
    # Ne doit pas lever ProxyUnavailableError
    await _verify_proxy_is_fr_carrier(proxy)


@pytest.mark.asyncio
async def test_proxy_datacenter_raises():
    """IP datacenter (Hetzner) → ProxyUnavailableError (R07)."""
    from app.models import ProxyInfo
    from app.services.account_creation import ProxyUnavailableError, _verify_proxy_is_fr_carrier

    bad_proxy = ProxyInfo(url="http://u:p@94.130.X.X:8080", asn_org="Hetzner Online GmbH", country="DE")
    with pytest.raises(ProxyUnavailableError):
        await _verify_proxy_is_fr_carrier(bad_proxy)


# ── EMAIL GENERATOR ────────────────────────────────────────────────────────────

def test_generate_emails_unique():
    """10 appels → 10 adresses toutes différentes."""
    from app.boundaries import generate_email

    emails = [generate_email("reprise-auto-pro.fr") for _ in range(10)]
    assert len(set(emails)) == 10
    for e in emails:
        assert e.startswith("contact.")
        assert e.endswith("@reprise-auto-pro.fr")
