"""
Fixtures pytest partagees.
Regle TDD : on mocke UNIQUEMENT boundaries.py - jamais PostgreSQL/Redis.
Les tests d'integration tournent sur une vraie DB de test (port 5433).
"""
import asyncio
import os
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://autotransfert:password@localhost:5433/autotransfert_p2_test",
)
os.environ.setdefault("APIFY_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
from app.config import get_settings
from app.main import app
from app.models import ActivationOrder, ProxyInfo, SmsResult, SmsStatus

get_settings().__dict__["control_tower_token"] = "test-control-token"
get_settings().__dict__["smstools_webhook_secret"] = "test-webhook-secret"
get_settings().__dict__["mailgun_webhook_signing_key"] = "test-mailgun-key"


@pytest.fixture(scope="session", autouse=True)
def create_db_tables():
    """Cree les tables de test si la base d'integration est disponible."""
    from app.db import Base, engine

    async def _create():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    try:
        asyncio.run(_create())
    except Exception:
        pass


@pytest.fixture(autouse=True)
def require_integration_db(request):
    if request.node.get_closest_marker("integration") is None:
        return

    from app.db import engine

    async def _ping():
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()

    try:
        asyncio.run(_ping())
    except Exception as exc:
        pytest.skip(f"DB d'integration indisponible: {exc}")


@pytest.fixture
async def workspace_record():
    from app.db import get_db
    from app.tables import Workspace

    async with get_db() as db:
        row = Workspace(name=f"Apify test {uuid.uuid4()}")
        db.add(row)
        await db.flush()
        row_id = row.id
    async with get_db() as db:
        yield await db.get(Workspace, row_id)


@pytest.fixture
async def running_campaign():
    from app.db import get_db
    from app.models import CampaignStatus
    from app.tables import Campaign

    async with get_db() as db:
        row = Campaign(
            type="sms_direct",
            message_template="Bonjour {title} {url}",
            status=CampaignStatus.RUNNING,
        )
        db.add(row)
        await db.flush()
        row_id = row.id
    async with get_db() as db:
        yield await db.get(Campaign, row_id)


@pytest.fixture
async def pending_campaign():
    from app.db import get_db
    from app.models import CampaignStatus
    from app.tables import Campaign

    async with get_db() as db:
        row = Campaign(
            type="sms_direct",
            message_template="Bonjour {title} {url}",
            status=CampaignStatus.PENDING,
        )
        db.add(row)
        await db.flush()
        row_id = row.id
    async with get_db() as db:
        yield await db.get(Campaign, row_id)


@pytest.fixture
async def existing_apify_account(workspace_record):
    from app.db import get_db
    from app.services.apify_secrets import ApifySecretCodec
    from app.tables import ApifyAccount

    settings = get_settings()
    codec = ApifySecretCodec(settings.apify_token_encryption_key, settings.secret_key)
    token = f"apify_api_{uuid.uuid4()}"
    webhook_secret = "test-apify-webhook-secret"
    async with get_db() as db:
        row = ApifyAccount(
            workspace_id=workspace_record.id,
            label=f"Compte {uuid.uuid4()}",
            apify_user_id=f"user-{uuid.uuid4()}",
            username="apify-test",
            token_ciphertext=codec.encrypt(token),
            token_fingerprint=codec.fingerprint(token),
            webhook_secret_ciphertext=codec.encrypt(webhook_secret),
            webhook_secret_hash=codec.fingerprint(webhook_secret),
        )
        db.add(row)
        await db.flush()
        row_id = row.id
    async with get_db() as db:
        yield await db.get(ApifyAccount, row_id)


@pytest.fixture
async def configured_apify_binding(
    workspace_record, existing_apify_account, running_campaign
):
    from app.db import get_db
    from app.services.apify_secrets import ApifySecretCodec
    from app.tables import ApifyActorBinding

    settings = get_settings()
    codec = ApifySecretCodec(settings.apify_token_encryption_key, settings.secret_key)
    async with get_db() as db:
        row = ApifyActorBinding(
            workspace_id=workspace_record.id,
            account_id=existing_apify_account.id,
            campaign_id=running_campaign.id,
            resource_type="actor",
            resource_id=f"owner/example-{uuid.uuid4()}",
            name="Example Actor",
            input_ciphertext=codec.encrypt("{}"),
            enabled=True,
        )
        db.add(row)
        await db.flush()
        row_id = row.id
    async with get_db() as db:
        yield await db.get(ApifyActorBinding, row_id)


@pytest.fixture
async def succeeded_apify_run(
    workspace_record, existing_apify_account, configured_apify_binding
):
    from app.db import get_db
    from app.tables import ApifyRun

    async with get_db() as db:
        row = ApifyRun(
            workspace_id=workspace_record.id,
            account_id=existing_apify_account.id,
            binding_id=configured_apify_binding.id,
            apify_run_id=f"run-{uuid.uuid4()}",
            status="SUCCEEDED",
            default_dataset_id="dataset-test-fixed",
        )
        db.add(row)
        await db.flush()
        row_id = row.id
    async with get_db() as db:
        yield await db.get(ApifyRun, row_id)


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={
            "X-Control-Tower-Token": "test-control-token",
            "X-Webhook-Secret": "test-webhook-secret",
        },
    ) as c:
        yield c


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
    with patch("app.boundaries.buy_number_with_fallback", new_callable=AsyncMock) as m:
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
