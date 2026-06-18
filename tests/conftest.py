"""
Fixtures pytest partagées.
Règle TDD : on mocke UNIQUEMENT boundaries.py — jamais PostgreSQL/Redis.
Les tests d'intégration tournent sur une vraie DB de test (port 5433).
"""
import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from app.main import app
from app.models import ActivationOrder, ProxyInfo, SmsResult, SmsStatus


# ── APP CLIENT ───────────────────────────────────────────────────────────────

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ── BOUNDARIES MOCKS ─────────────────────────────────────────────────────────

@pytest.fixture
def mock_send_sms():
    with patch("app.boundaries.send_sms", new_callable=AsyncMock) as m:
        m.return_value = SmsResult(
            id="msg_test_001",
            status=SmsStatus.SENT,
            cost=0.042,
            sim_id="sim_01",
            to="+33612345678",
        )
        yield m


@pytest.fixture
def mock_buy_number():
    with patch("app.boundaries.buy_number", new_callable=AsyncMock) as m:
        m.return_value = ActivationOrder(
            id="order_test_001",
            phone="+33712345678",
            country="france",
            service="leboncoin",
            cost=0.28,
            expires=9999999999,
        )
        yield m


@pytest.fixture
def mock_poll_sms():
    with patch("app.boundaries.poll_sms", new_callable=AsyncMock) as m:
        m.return_value = "847291"
        yield m


@pytest.fixture
def mock_get_4g_proxy():
    with patch("app.boundaries.get_4g_proxy", new_callable=AsyncMock) as m:
        m.return_value = ProxyInfo(
            url="http://user:pass@185.10.20.30:8080",
            asn_org="Orange",
            country="FR",
        )
        yield m


@pytest.fixture
def mock_rotate_4g_ip():
    with patch("app.boundaries.rotate_4g_ip", new_callable=AsyncMock) as m:
        m.return_value = True
        yield m


@pytest.fixture
def mock_get_sim_list():
    with patch("app.boundaries.get_sim_list", new_callable=AsyncMock) as m:
        m.return_value = [
            {"id": "sim_01", "status": "active", "quota_remaining": 15},
            {"id": "sim_02", "status": "active", "quota_remaining": 12},
            {"id": "sim_03", "status": "active", "quota_remaining": 8},
        ]
        yield m
