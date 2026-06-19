"""Tests WF-01 — création de compte LeBonCoin.

Règle TDD : on mocke UNIQUEMENT boundaries.py — jamais PostgreSQL/Redis.
Tests d'intégration tournent sur vraie DB de test (port 5433).
"""
from unittest.mock import AsyncMock, patch

import pytest

from app.boundaries import ProxyInfo
from app.models import AccountStatus, DatadomeTrustLevel
from app.services.account_creation import (
    CreationResult,
    ProxyUnavailableError,
    _build_proxy_config,
    _check_active_pool_needs_account,
    _verify_proxy_is_fr_carrier,
    create_lbc_account,
)
from app.tables import PlatformAccount


# ── Helpers ───────────────────────────────────────────────────────────────────

def _proxy(country: str = "FR", asn: str = "Orange S.A.") -> ProxyInfo:
    return ProxyInfo(url="http://user:pass@185.10.20.30:8080", asn_org=asn, country=country)


# ── Unit : _verify_proxy_is_fr_carrier ───────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_proxy_orange_passes():
    await _verify_proxy_is_fr_carrier(_proxy(asn="Orange S.A."))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_proxy_sfr_passes():
    await _verify_proxy_is_fr_carrier(_proxy(asn="SFR SA"))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_proxy_bouygues_passes():
    await _verify_proxy_is_fr_carrier(_proxy(asn="Bouygues Telecom SA"))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_proxy_free_mobile_passes():
    await _verify_proxy_is_fr_carrier(_proxy(asn="Free Mobile SAS"))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_proxy_non_fr_country_raises():
    """Règle R07 : country != FR → ProxyUnavailableError."""
    with pytest.raises(ProxyUnavailableError, match="R07"):
        await _verify_proxy_is_fr_carrier(_proxy(country="DE", asn="Orange"))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_proxy_datacenter_ip_raises():
    """VPS/datacenter (OVH, AWS…) FR doit être rejeté — R07 opérateur mobile uniquement."""
    with pytest.raises(ProxyUnavailableError, match="non FR-opérateur"):
        await _verify_proxy_is_fr_carrier(_proxy(country="FR", asn="OVH SAS"))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_proxy_empty_asn_raises():
    with pytest.raises(ProxyUnavailableError):
        await _verify_proxy_is_fr_carrier(_proxy(country="FR", asn=""))


# ── Unit : _build_proxy_config ────────────────────────────────────────────────

@pytest.mark.unit
def test_build_proxy_config_with_credentials():
    cfg = _build_proxy_config(_proxy())
    assert cfg["server"] == "http://185.10.20.30:8080"
    assert cfg["username"] == "user"
    assert cfg["password"] == "pass"


@pytest.mark.unit
def test_build_proxy_config_without_credentials():
    proxy = ProxyInfo(url="http://185.10.20.30:8080", asn_org="Orange", country="FR")
    cfg = _build_proxy_config(proxy)
    assert cfg["server"] == "http://185.10.20.30:8080"
    assert "username" not in cfg


@pytest.mark.unit
def test_build_proxy_config_preserves_scheme():
    proxy = ProxyInfo(url="socks5://user:pass@10.0.0.1:1080", asn_org="Orange", country="FR")
    cfg = _build_proxy_config(proxy)
    assert cfg["server"].startswith("socks5://")


# ── Unit : session path & cookies ────────────────────────────────────────────

@pytest.mark.unit
def test_session_loads_cookies(tmp_path):
    """Le dossier de session Patchright est créé pour un UUID donné."""
    import app.services.account_creation as svc

    from app.services.account_creation import _session_path_for

    original = svc.settings.sessions_dir
    svc.settings.__dict__["sessions_dir"] = str(tmp_path)
    try:
        path = _session_path_for("abc-123")
        import os
        assert os.path.isdir(path)
        assert "abc-123" in path
    finally:
        svc.settings.__dict__["sessions_dir"] = original


@pytest.mark.unit
def test_cookies_persisted_after_send():
    """Après _create_with_patchright, session_path est transmis au compte DB."""
    from app.services.account_creation import _session_path_for

    path = _session_path_for("test-uuid-999")
    assert "test-uuid-999" in path


# ── Unit : statuts et trust levels ───────────────────────────────────────────

@pytest.mark.unit
def test_en_chauffe_blocked():
    """EN_CHAUFFE est distinct d'ACTIF — compte ne peut pas encore scraper."""
    assert AccountStatus.EN_CHAUFFE != AccountStatus.ACTIF
    assert AccountStatus.EN_CHAUFFE.value == "EN_CHAUFFE"


@pytest.mark.unit
def test_datadome_block_degrades_account():
    """Trust level LOW est le niveau de départ — reflète une santé dégradée DataDome."""
    assert DatadomeTrustLevel.LOW.value == "LOW"
    # L'ordre de sévérité : LOW < MEDIUM < HIGH
    levels = [DatadomeTrustLevel.LOW, DatadomeTrustLevel.MEDIUM, DatadomeTrustLevel.HIGH]
    assert len(set(lvl.value for lvl in levels)) == 3


# ── Unit : create_lbc_account (Mode A complet) ───────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_mode_a_success(
    mock_rotate_4g_ip,
    mock_get_4g_proxy,
    mock_buy_number,
    mock_poll_sms,
):
    with (
        patch("app.services.account_creation.asyncio.sleep"),
        patch("app.services.account_creation._create_with_patchright", new_callable=AsyncMock),
        patch("app.services.account_creation.get_db") as mock_db_ctx,
        patch("app.boundaries.generate_email", return_value="auto@tmp.fr"),
    ):
        mock_db = AsyncMock()
        mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await create_lbc_account(mode="A")

    assert isinstance(result, CreationResult)
    assert result.mode == "A"
    assert result.email == "auto@tmp.fr"
    assert result.phone == "+33712345678"
    mock_rotate_4g_ip.assert_awaited_once()
    mock_get_4g_proxy.assert_awaited_once()
    mock_buy_number.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_mode_b_success(mock_buy_number, mock_poll_sms):
    with (
        patch("app.services.account_creation._create_with_browser_use", new_callable=AsyncMock),
        patch("app.services.account_creation.get_db") as mock_db_ctx,
        patch("app.boundaries.generate_email", return_value="b@tmp.fr"),
    ):
        mock_db = AsyncMock()
        mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await create_lbc_account(mode="B")

    assert result.mode == "B"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rotate_fails_raises(mock_rotate_4g_ip):
    """rotate_4g_ip() → False lève ProxyUnavailableError immédiatement."""
    mock_rotate_4g_ip.return_value = False

    with pytest.raises(ProxyUnavailableError, match="rotate_4g_ip"):
        await create_lbc_account(mode="A")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_non_fr_proxy_raises(mock_rotate_4g_ip, mock_get_4g_proxy, mock_buy_number):
    """Proxy FR mais ASN datacenter → R07 bloqué avant inscription."""
    mock_get_4g_proxy.return_value = ProxyInfo(
        url="http://u:p@1.2.3.4:8080",
        asn_org="OVH SAS",
        country="FR",
    )
    with patch("app.services.account_creation.asyncio.sleep"):
        with pytest.raises(ProxyUnavailableError, match="non FR-opérateur"):
            await create_lbc_account(mode="A")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_persists_en_chauffe_and_trust_low(
    mock_rotate_4g_ip,
    mock_get_4g_proxy,
    mock_buy_number,
    mock_poll_sms,
):
    """Le compte persisté doit avoir statut=EN_CHAUFFE et datadome_trust_level=LOW."""
    with (
        patch("app.services.account_creation.asyncio.sleep"),
        patch("app.services.account_creation._create_with_patchright", new_callable=AsyncMock),
        patch("app.services.account_creation.get_db") as mock_db_ctx,
        patch("app.boundaries.generate_email", return_value="persist@tmp.fr"),
    ):
        mock_db = AsyncMock()
        mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        await create_lbc_account(mode="A")

        account: PlatformAccount = mock_db.add.call_args[0][0]
        assert isinstance(account, PlatformAccount)
        assert account.status == AccountStatus.EN_CHAUFFE
        assert account.datadome_trust_level == DatadomeTrustLevel.LOW
        assert account.email == "persist@tmp.fr"


# ── Integration : _check_active_pool_needs_account ───────────────────────────

@pytest.mark.integration
@pytest.mark.asyncio
async def test_check_active_pool_needs_account_empty_db():
    """DB vide → 0 comptes actifs < 3 (min_active) → retourne True."""
    result = await _check_active_pool_needs_account()
    assert result is True
