# Apify Multi-Account Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connecter plusieurs comptes Apify, piloter leurs Actors et Tasks, normaliser automatiquement leurs Datasets en leads et demarrer une unique sequence SMS conforme des qu'un numero exploitable est importe.

**Architecture:** FastAPI expose l'administration et un webhook Apify, Celery lance et reconcilie les runs, PostgreSQL conserve secrets chiffres, runs, items et profils, et `app/boundaries.py` reste l'unique frontiere HTTP externe. Le normaliseur deterministe utilise les schemas et les valeurs avant un fallback IA borne ; les profils candidats sont evalues en mode fantome avant promotion.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, Alembic, PostgreSQL, Celery/Redis, `apify-client` 3.x, `cryptography` Fernet, `phonenumbers`, Pydantic 2, Next.js, React, Radix Themes, Vitest/MSW.

---

## File map

### Backend files to create

- `app/api/apify.py` — API protegee comptes, catalogue, bindings, runs, items et profils.
- `app/webhooks/apify.py` — reception rapide et idempotente des fins de run.
- `app/services/apify_secrets.py` — chiffrement, dechiffrement et empreinte des secrets.
- `app/services/apify_accounts.py` — comptes, catalogue et bindings.
- `app/services/apify_runs.py` — lancement, statut, planification et reconciliation.
- `app/services/apify_normalizer.py` — aplatissement, candidats, scoring et modele canonique.
- `app/services/apify_ingestion.py` — import pagine, persistance et demarrage de sequence.
- `app/services/apify_learning.py` — profils candidats, replay fantome et keep/discard.
- `migrations/versions/q7h8i9j0k1l2_add_apify_ingestion.py` — schema Apify et generalisation SMS.
- `tests/test_apify_secrets.py`
- `tests/test_apify_accounts.py`
- `tests/test_apify_boundaries.py`
- `tests/test_apify_normalizer.py`
- `tests/test_apify_ingestion.py`
- `tests/test_apify_webhook.py`
- `tests/test_apify_learning.py`
- `tests/test_apify_api.py`
- `tests/test_apify_e2e.py`

### Backend files to modify

- `pyproject.toml` — clients Apify et Fernet.
- `.env.example` — cle maitre et reglages sans valeur secrete.
- `app/config.py` — configuration Apify validee.
- `app/tables.py` — entites Apify et contexte generique SMS.
- `app/models.py` — enums et contrats Pydantic.
- `app/boundaries.py` — appels Apify et fallback IA externe.
- `app/services/sms_sequence.py` — sequence contact/campagne, contexte optionnel et R01.
- `app/services/connector_monitor.py` — etat global Apify.
- `app/tasks.py` — lancement, import, reconciliation et evaluation.
- `app/main.py` — montage des routes protegees et du webhook.
- `tests/conftest.py` — cle de test et mocks de frontiere.
- `tests/test_sms_sequence.py` — fenetre SMS et contexte sans Listing.

### Frontend files to create

- `front/lib/apify-api.ts` — types et lectures serveur.
- `front/app/apify/page.tsx` — page Control Tower Apify.
- `front/app/api/apify/[...path]/route.ts` — proxy BFF multi-methodes.
- `front/components/ApifyControlCenter.tsx` — navigation des panneaux et rafraichissement.
- `front/components/ApifyAccountsPanel.tsx` — comptes et secrets en ecriture seule.
- `front/components/ApifyBindingsPanel.tsx` — Actors, Tasks, campagne et planification.
- `front/components/ApifyRunsPanel.tsx` — runs et rejeu idempotent.
- `front/components/ApifyResultsPanel.tsx` — brut/normalise masque et filtres.
- `front/components/ApifyLearningPanel.tsx` — profils, experiences et exceptions.
- `front/components/ApifyControlCenter.test.tsx`

### Frontend and documentation files to modify

- `front/components/NavLinks.tsx` — entree Apify.
- `front/components/ConnectorControlPanel.tsx` — carte Apify et lien detaille.
- `front/lib/api.ts` — types de connecteur maintenus.
- `front/tests/handlers.ts` — fixtures MSW Apify.
- `front/tests/components.test.tsx` — navigation et carte connecteur.
- `docs/CONTROL_TOWER_OPERATIONS.md` — runbook, rotation et incidents.
- `docs/GUIDE_COMPLET_UTILISATION.md` — utilisation de la nouvelle section.
- `docs/Plan_Implementation_Modules.html` — concordance R01 et fournisseur d'ingestion.

---

### Task 1: Dependencies, configuration, and secret codec

**Files:**
- Modify: `pyproject.toml`
- Modify: `.env.example`
- Modify: `app/config.py`
- Create: `app/services/apify_secrets.py`
- Create: `tests/test_apify_secrets.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Write failing tests for encryption and configuration**

```python
# tests/test_apify_secrets.py
from cryptography.fernet import Fernet
import pytest

from app.services.apify_secrets import ApifySecretCodec


def test_secret_codec_round_trip_and_masking():
    codec = ApifySecretCodec(Fernet.generate_key().decode(), "app-test-secret")
    encrypted = codec.encrypt("apify_api_secret")

    assert encrypted != b"apify_api_secret"
    assert codec.decrypt(encrypted) == "apify_api_secret"
    assert codec.mask("apify_api_secret") == "apif...cret"


def test_secret_codec_fingerprint_is_stable_without_exposing_token():
    codec = ApifySecretCodec(Fernet.generate_key().decode(), "app-test-secret")
    first = codec.fingerprint("apify_api_secret")
    second = codec.fingerprint("apify_api_secret")

    assert first == second
    assert "apify_api_secret" not in first


def test_secret_codec_rejects_missing_master_key():
    with pytest.raises(RuntimeError, match="APIFY_TOKEN_ENCRYPTION_KEY"):
        ApifySecretCodec("", "app-test-secret")
```

- [ ] **Step 2: Run the tests and verify the missing module failure**

Run: `python -m pytest tests/test_apify_secrets.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: app.services.apify_secrets`.

- [ ] **Step 3: Add pinned dependency ranges and settings**

Add to `pyproject.toml`:

```toml
    "apify-client>=3.0.6,<4.0.0",
    "cryptography>=49.0.0,<50.0.0",
```

Add to `.env.example` without a real value:

```dotenv
APIFY_TOKEN_ENCRYPTION_KEY=
APIFY_RECONCILE_MINUTES=5
APIFY_IMPORT_PAGE_SIZE=250
APIFY_AI_FALLBACK_ENABLED=false
```

Add to `Settings`:

```python
    # Apify multi-account integration
    apify_token_encryption_key: str = ""
    apify_reconcile_minutes: int = 5
    apify_import_page_size: int = 250
    apify_ai_fallback_enabled: bool = False
```

Extend `validate_startup_settings()` so production fails only when at least one
Apify account is used without a key at runtime; do not make a fresh deployment
fail before the first account exists. Validate numeric settings directly:

```python
        if self.apify_reconcile_minutes < 1:
            raise ValueError("apify_reconcile_minutes must be positive")
        if not 1 <= self.apify_import_page_size <= 1000:
            raise ValueError("apify_import_page_size must be between 1 and 1000")
```

- [ ] **Step 4: Implement the minimal codec**

```python
# app/services/apify_secrets.py
import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken


class ApifySecretCodec:
    def __init__(self, encryption_key: str, fingerprint_key: str):
        if not encryption_key:
            raise RuntimeError("APIFY_TOKEN_ENCRYPTION_KEY is required")
        self._fernet = Fernet(encryption_key.encode())
        self._fingerprint_key = fingerprint_key.encode()

    def encrypt(self, value: str) -> bytes:
        return self._fernet.encrypt(value.encode())

    def decrypt(self, value: bytes) -> str:
        try:
            return self._fernet.decrypt(value).decode()
        except InvalidToken as exc:
            raise RuntimeError("Unable to decrypt Apify secret") from exc

    def fingerprint(self, value: str) -> str:
        return hmac.new(
            self._fingerprint_key, value.encode(), hashlib.sha256
        ).hexdigest()

    @staticmethod
    def mask(value: str) -> str:
        if len(value) <= 8:
            return "********"
        return f"{value[:4]}...{value[-4:]}"
```

- [ ] **Step 5: Configure a generated test key before importing the app**

In `tests/conftest.py`, before `from app.config import get_settings`, add:

```python
from cryptography.fernet import Fernet

os.environ.setdefault("APIFY_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
```

- [ ] **Step 6: Run focused tests and lint**

Run: `python -m pytest tests/test_apify_secrets.py -q`

Expected: `3 passed`.

Run: `python -m ruff check app/services/apify_secrets.py app/config.py tests/test_apify_secrets.py`

Expected: exit code 0.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .env.example app/config.py app/services/apify_secrets.py tests/conftest.py tests/test_apify_secrets.py
git commit -m "feat: add secure Apify configuration"
```

---

### Task 2: Database schema and SMS target migration

**Files:**
- Modify: `app/tables.py`
- Create: `migrations/versions/q7h8i9j0k1l2_add_apify_ingestion.py`
- Create: `tests/test_apify_schema.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Write an integration test for constraints and defaults**

```python
# tests/test_apify_schema.py
import pytest
from sqlalchemy import select

from app.db import get_db
from app.tables import ApifyAccount, ApifyActorBinding, Workspace


@pytest.mark.integration
async def test_apify_account_and_binding_are_workspace_scoped(workspace_record):
    async with get_db() as db:
        account = ApifyAccount(
            workspace_id=workspace_record.id,
            label="Compte principal",
            apify_user_id="user-1",
            username="demo",
            token_ciphertext=b"ciphertext",
            token_fingerprint="f" * 64,
            webhook_secret_ciphertext=b"webhook-ciphertext",
            webhook_secret_hash="w" * 64,
        )
        db.add(account)
        await db.flush()
        binding = ApifyActorBinding(
            workspace_id=workspace_record.id,
            account_id=account.id,
            resource_type="actor",
            resource_id="owner/example",
            name="Example",
            enabled=False,
        )
        db.add(binding)

    async with get_db() as db:
        stored = (
            await db.execute(
                select(ApifyActorBinding).where(
                    ApifyActorBinding.resource_id == "owner/example"
                )
            )
        ).scalar_one()
        assert stored.enabled is False
```

- [ ] **Step 2: Run the schema test and verify it fails**

Run: `python -m pytest tests/test_apify_schema.py -q`

Expected: FAIL because `ApifyAccount` and `ApifyActorBinding` do not exist.

- [ ] **Step 3: Add the SQLAlchemy entities**

Add focused classes to `app/tables.py` with UUID primary keys and timezone-aware
timestamps. The minimum shared constraints are:

```python
class ApifyAccount(Base):
    __tablename__ = "apify_accounts"
    __table_args__ = (
        UniqueConstraint("workspace_id", "label", name="uq_apify_account_label"),
        UniqueConstraint(
            "workspace_id", "token_fingerprint", name="uq_apify_account_token"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    apify_user_id: Mapped[str] = mapped_column(String(120), nullable=False)
    username: Mapped[str] = mapped_column(String(120), nullable=False)
    token_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    token_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    webhook_secret_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    webhook_secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ApifyActorBinding(Base):
    __tablename__ = "apify_actor_bindings"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "resource_type", "resource_id",
            name="uq_apify_binding_resource",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("apify_accounts.id", ondelete="CASCADE"), index=True)
    sector_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sectors.id"), index=True)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("campaigns.id"), index=True)
    resource_type: Mapped[str] = mapped_column(String(10), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    input_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    schedule_authority: Mapped[str] = mapped_column(String(10), default="internal", nullable=False)
    schedule_minutes: Mapped[int | None] = mapped_column(Integer)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    webhook_id: Mapped[str | None] = mapped_column(String(120))
    schema_fingerprint: Mapped[str | None] = mapped_column(String(64))
    active_profile_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    suspended_reason: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ApifyRun(Base):
    __tablename__ = "apify_runs"
    __table_args__ = (
        UniqueConstraint("account_id", "apify_run_id", name="uq_apify_remote_run"),
    )


class ApifyItem(Base):
    __tablename__ = "apify_items"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "run_id", "dataset_index", "content_hash",
            name="uq_apify_dataset_item",
        ),
    )
    # raw_payload and normalized_payload use JSON, links are nullable foreign keys


class ApifyNormalizationProfile(Base):
    __tablename__ = "apify_normalization_profiles"


class ApifyNormalizationExperiment(Base):
    __tablename__ = "apify_normalization_experiments"


class ApifyException(Base):
    __tablename__ = "apify_exceptions"
```

Use strings for provider states so a third-party state addition does not require
a PostgreSQL enum migration. Add indexes on status, next run, remote run ID,
dataset ID, item status and exception status.

Use the column table in the approved design for `ApifyRun`, `ApifyItem`,
`ApifyNormalizationProfile`, `ApifyNormalizationExperiment` and
`ApifyException`. Translate every named field into a concrete mapped column;
JSON payloads use `JSON`, error text uses `Text`, provider identifiers use
`String(120)`, and all links use UUID foreign keys with explicit delete behavior.

- [ ] **Step 4: Generalize `SmsSequence` safely**

Change `listing_id` to nullable, add `context_json: JSON` with `{}` default, and
replace the listing uniqueness rule with:

```python
__table_args__ = (
    UniqueConstraint(
        "contact_id", "campaign_id", name="uq_sms_sequence_contact_campaign"
    ),
)
```

- [ ] **Step 5: Write the Alembic migration**

Create revision `q7h8i9j0k1l2` with `down_revision = "p6g7h8i9j0k1"`. The
migration must create the seven Apify tables, then deduplicate historical
sequences before adding the new unique constraint:

```python
op.execute("""
DELETE FROM sms_sequences duplicate
USING sms_sequences keeper
WHERE duplicate.contact_id = keeper.contact_id
  AND duplicate.campaign_id = keeper.campaign_id
  AND duplicate.created_at > keeper.created_at
""")
op.drop_constraint("uq_sms_sequence_listing_campaign", "sms_sequences", type_="unique")
op.alter_column("sms_sequences", "listing_id", nullable=True)
op.add_column(
    "sms_sequences",
    sa.Column("context_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
)
op.create_unique_constraint(
    "uq_sms_sequence_contact_campaign",
    "sms_sequences",
    ["contact_id", "campaign_id"],
)
```

The downgrade restores the old constraint only after deleting generic sequences
whose `listing_id IS NULL`; document this destructive downgrade inside the
migration docstring.

- [ ] **Step 6: Apply migrations and run the integration test**

Before running it, add deterministic integration fixtures to
`tests/conftest.py`. Each fixture creates a unique row and returns it after the
transaction commits:

```python
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
```

Add `import uuid` to `tests/conftest.py`, then add `pending_campaign` with
`CampaignStatus.PENDING`, `existing_apify_account`
with a codec-encrypted test token, `configured_apify_binding` linked to the
running campaign, and `succeeded_apify_run` with a fixed Dataset ID. Reuse these
fixtures in later tasks instead of constructing conflicting global rows.

Run: `python -m alembic upgrade head`

Expected: revision `q7h8i9j0k1l2` applies successfully.

Run: `python -m pytest tests/test_apify_schema.py -q`

Expected: PASS when the integration database is available, otherwise SKIP.

- [ ] **Step 7: Commit**

```bash
git add app/tables.py migrations/versions/q7h8i9j0k1l2_add_apify_ingestion.py tests/test_apify_schema.py
git commit -m "feat: add Apify persistence schema"
```

---

### Task 3: Pydantic contracts and provider enums

**Files:**
- Modify: `app/models.py`
- Create: `tests/test_apify_models.py`

- [ ] **Step 1: Write failing contract tests**

```python
# tests/test_apify_models.py
import pytest
from pydantic import ValidationError

from app.models import ApifyAccountCreate, ApifyBindingCreate


def test_account_token_is_write_only_input():
    payload = ApifyAccountCreate(label="Principal", token="apify_api_token_123")
    assert payload.token.get_secret_value() == "apify_api_token_123"


def test_binding_requires_one_scheduling_authority():
    with pytest.raises(ValidationError, match="scheduling authority"):
        ApifyBindingCreate(
            account_id="123e4567-e89b-12d3-a456-426614174000",
            resource_type="actor",
            resource_id="owner/demo",
            campaign_id="123e4567-e89b-12d3-a456-426614174001",
            schedule_authority="internal",
            schedule_minutes=None,
        )
```

- [ ] **Step 2: Run the tests and verify missing model failures**

Run: `python -m pytest tests/test_apify_models.py -q`

Expected: FAIL importing `ApifyAccountCreate`.

- [ ] **Step 3: Add explicit enums and contracts**

Add `StrEnum` values for account, resource, run, item, profile, experiment and
exception states. Add Pydantic models with `from_attributes=True` outputs:

```python
class ApifyAccountCreate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    token: SecretStr


class ApifyBindingCreate(BaseModel):
    account_id: UUID
    resource_type: Literal["actor", "task"]
    resource_id: str = Field(min_length=1, max_length=255)
    name: str | None = Field(default=None, max_length=255)
    sector_id: UUID | None = None
    campaign_id: UUID
    input: dict[str, Any] = Field(default_factory=dict)
    schedule_authority: Literal["internal", "apify"] = "internal"
    schedule_minutes: int | None = Field(default=60, ge=5, le=10080)

    @model_validator(mode="after")
    def validate_schedule(self):
        if self.schedule_authority == "internal" and self.schedule_minutes is None:
            raise ValueError("internal scheduling authority requires schedule_minutes")
        if self.schedule_authority == "apify" and self.schedule_minutes is not None:
            raise ValueError("Apify scheduling authority forbids schedule_minutes")
        return self
```

Also define masked account output, catalog resource, binding output, run page,
item page, profile/experiment view, exception view, webhook payload and dashboard
summary. `ApifyAccountOut` must not contain `token_ciphertext`, `token` or input
secrets.

Update `SmsSequenceOut.listing_id` to `UUID | None` and add
`context_json: dict[str, Any]`.

- [ ] **Step 4: Run contract tests and model import smoke test**

Run: `python -m pytest tests/test_apify_models.py tests/test_sms_sequence.py -q`

Expected: all tests pass.

Run: `python -m ruff check app/models.py tests/test_apify_models.py`

Expected: exit code 0.

- [ ] **Step 5: Commit**

```bash
git add app/models.py tests/test_apify_models.py
git commit -m "feat: define Apify API contracts"
```

---

### Task 4: Apify boundary client

**Files:**
- Modify: `app/boundaries.py`
- Create: `tests/test_apify_boundaries.py`

- [ ] **Step 1: Write failing boundary tests with a fake client**

```python
# tests/test_apify_boundaries.py
from unittest.mock import AsyncMock, MagicMock

import pytest

from app import boundaries


@pytest.mark.asyncio
async def test_apify_start_resource_uses_actor_or_task(monkeypatch):
    actor = AsyncMock()
    actor.start.return_value = {"id": "run-1", "status": "READY"}
    client = MagicMock()
    client.close = AsyncMock()
    client.actor.return_value = actor
    monkeypatch.setattr(boundaries, "_apify_client", lambda token: client)

    run = await boundaries.apify_start_resource(
        "secret", "actor", "owner/demo", {"limit": 10}
    )

    assert run["id"] == "run-1"
    actor.start.assert_awaited_once_with(run_input={"limit": 10})


@pytest.mark.asyncio
async def test_apify_iter_dataset_preserves_indexes(monkeypatch):
    dataset = MagicMock()
    dataset.iterate_items.return_value = _async_items([{"phone": "0612345678"}])
    client = MagicMock()
    client.close = AsyncMock()
    client.dataset.return_value = dataset
    monkeypatch.setattr(boundaries, "_apify_client", lambda token: client)

    rows = [row async for row in boundaries.apify_iter_dataset("secret", "ds-1")]
    assert rows == [(0, {"phone": "0612345678"})]


async def _async_items(items):
    for item in items:
        yield item
```

- [ ] **Step 2: Run the boundary tests and verify missing functions**

Run: `python -m pytest tests/test_apify_boundaries.py -q`

Expected: FAIL because `apify_start_resource` is absent.

- [ ] **Step 3: Add narrow boundary functions**

Use `ApifyClientAsync(token=token, max_retries=5, connect_timeout_secs=10,
request_timeout_secs=60)` and implement only the following public functions.
Each function creates a client, executes one bounded operation and closes the
client in `finally`:

```python
async def apify_iter_dataset(
    token: str, dataset_id: str
) -> AsyncIterator[tuple[int, dict]]:
    client = _apify_client(token)
    try:
        index = 0
        async for item in client.dataset(dataset_id).iterate_items():
            yield index, dict(item)
            index += 1
    finally:
        await client.close()
```

The other public functions are `apify_validate_token`, `apify_list_actors`,
`apify_list_tasks`, `apify_start_resource`, `apify_get_run`,
`apify_list_recent_runs`, `apify_create_webhook` and
`apify_delete_webhook`. Return plain dictionaries/lists copied from client
responses so no Apify client object escapes the boundary. Resource start chooses
`client.actor(resource_id).start(run_input=run_input)` or
`client.task(resource_id).start(task_input=run_input)` according to
`resource_type`; reject any other value before the API call.

For Datasets use `iterate_items()` so the official client owns pagination. For
webhooks configure success, failure, abort and timeout events, a minimal payload
with `eventType` and `resource`, and an `Authorization: Bearer <secret>` header
template. Never log `token`, `run_input` or `secret`.

- [ ] **Step 4: Run tests and lint**

Run: `python -m pytest tests/test_apify_boundaries.py -q`

Expected: all tests pass.

Run: `python -m ruff check app/boundaries.py tests/test_apify_boundaries.py`

Expected: exit code 0.

- [ ] **Step 5: Commit**

```bash
git add app/boundaries.py tests/test_apify_boundaries.py
git commit -m "feat: add Apify API boundary"
```

---

### Task 5: Account, catalog, and binding services

**Files:**
- Create: `app/services/apify_accounts.py`
- Create: `tests/test_apify_accounts.py`

- [ ] **Step 1: Write integration tests for account creation and binding validation**

```python
# tests/test_apify_accounts.py
from unittest.mock import AsyncMock, patch

import pytest

from app.models import ApifyAccountCreate, ApifyBindingCreate
from app.services.apify_accounts import create_account, create_binding


@pytest.mark.integration
@patch("app.boundaries.apify_validate_token", new_callable=AsyncMock)
async def test_create_account_validates_and_never_returns_token(validate):
    validate.return_value = {"id": "user-1", "username": "owner"}
    account = await create_account(
        ApifyAccountCreate(label="Principal", token="apify_api_secret")
    )

    assert account.username == "owner"
    assert account.token_masked == "apif...cret"
    assert not hasattr(account, "token")


@pytest.mark.integration
async def test_binding_rejects_inactive_campaign(existing_apify_account, pending_campaign):
    with pytest.raises(ValueError, match="campaign_not_running"):
        await create_binding(
            ApifyBindingCreate(
                account_id=existing_apify_account.id,
                resource_type="actor",
                resource_id="owner/demo",
                campaign_id=pending_campaign.id,
                schedule_authority="internal",
                schedule_minutes=60,
            )
        )
```

- [ ] **Step 2: Run tests and verify missing service failure**

Run: `python -m pytest tests/test_apify_accounts.py -q`

Expected: FAIL importing `app.services.apify_accounts`.

- [ ] **Step 3: Implement account lifecycle**

Implement `create_account(payload)`, `list_accounts()`,
`replace_account_token(account_id, token)`, `suspend_account(account_id)`,
`delete_account(account_id)` and `sync_catalog(account_id)` with `get_db()`
transactions and audit events. Use one private `_account_output(row)` function
to construct `ApifyAccountOut` from an ORM row and its masked token; this keeps
encrypted columns out of every response by construction.

`create_account` validates first, encrypts second, detects the fingerprint,
generates a per-account webhook secret with `secrets.token_urlsafe(32)`, stores
its encrypted value plus HMAC, then
persists. `delete_account` must first delete remote webhooks and then delete the
account; if remote deletion fails, suspend locally and surface a retryable error.

- [ ] **Step 4: Implement binding lifecycle and automatic defaults**

Implement `create_binding(payload)`, `list_bindings()`,
`update_binding(binding_id, payload)` and
`set_binding_enabled(binding_id, enabled)`. Centralize all activation checks in
`_validate_binding_activation(db, binding)` so create, update and enable cannot
apply different rules.

Activation requires an active account, a `RUNNING` campaign, one scheduling
authority and a valid resource in the synchronized catalog. Resolve sector in
this order: explicit binding, campaign search criteria department/region, first
active workspace sector. If none exists, keep the binding disabled and return
`sector_required`.

When a binding becomes enabled, decrypt the per-account webhook secret, call
`boundaries.apify_create_webhook` for that resource and persist the returned
`webhook_id`. When disabled, delete that remote webhook before clearing the ID.
Store the complete input dictionary only as one encrypted JSON blob.

- [ ] **Step 5: Run focused integration tests**

Run: `python -m pytest tests/test_apify_accounts.py -q`

Expected: all available integration tests pass.

Run: `python -m ruff check app/services/apify_accounts.py tests/test_apify_accounts.py`

Expected: exit code 0.

- [ ] **Step 6: Commit**

```bash
git add app/services/apify_accounts.py tests/test_apify_accounts.py
git commit -m "feat: manage Apify accounts and bindings"
```

---

### Task 6: Generalize SMS sequences and enforce R01

**Files:**
- Modify: `app/services/sms_sequence.py`
- Modify: `app/models.py`
- Modify: `tests/test_sms_sequence.py`

- [ ] **Step 1: Add failing tests for generic context, deduplication, and hours**

```python
# append to tests/test_sms_sequence.py
import pytest
from unittest.mock import AsyncMock, patch

from app.services.sms_sequence import ensure_contact_sequence, run_due_sms_sequences


@pytest.mark.integration
async def test_generic_lead_creates_one_sequence_per_contact_campaign(running_campaign):
    first = await ensure_contact_sequence(
        phone="06 12 34 56 78",
        campaign_id=running_campaign.id,
        context={"title": "Lead Apify", "url": ""},
    )
    second = await ensure_contact_sequence(
        phone="+33612345678",
        campaign_id=running_campaign.id,
        context={"title": "Lead enrichi", "url": ""},
    )
    assert first["sequence_id"] == second["sequence_id"]


@pytest.mark.integration
@patch("app.boundaries.send_sms", new_callable=AsyncMock)
async def test_due_sequence_does_not_send_outside_paris_window(send_sms):
    result = await run_due_sms_sequences(
        now=datetime(2026, 7, 16, 3, 0, tzinfo=UTC)
    )
    assert result["status"] == "outside_window"
    send_sms.assert_not_awaited()
```

- [ ] **Step 2: Run tests and verify failures against current behavior**

Run: `python -m pytest tests/test_sms_sequence.py -q`

Expected: FAIL because `ensure_contact_sequence` is missing and R01 is not enforced.

- [ ] **Step 3: Introduce a session-aware sequence primitive**

```python
async def ensure_contact_sequence_in_session(
    db: AsyncSession,
    *,
    phone: str,
    campaign_id: UUID,
    listing_id: UUID | None = None,
    context: dict | None = None,
) -> dict:
    """Create or reuse one contact/campaign sequence inside caller transaction."""
    normalized = extract_phone(phone)
    if not normalized:
        raise ValueError("invalid_phone")
    if await is_blacklisted(normalized):
        return {"created": False, "status": "blacklisted", "phone": normalized}
    campaign = await db.get(Campaign, campaign_id)
    if campaign is None or campaign.status != CampaignStatus.RUNNING.value:
        raise ValueError("campaign_not_running")
    contact = await db.scalar(select(Contact).where(Contact.phone_e164 == normalized))
    if contact is None:
        contact = Contact(phone_e164=normalized)
        db.add(contact)
        await db.flush()
    sequence = await db.scalar(
        select(SmsSequence).where(
            SmsSequence.contact_id == contact.id,
            SmsSequence.campaign_id == campaign_id,
        )
    )
    if sequence is None:
        sequence = SmsSequence(
            contact_id=contact.id,
            listing_id=listing_id,
            campaign_id=campaign_id,
            context_json=context or {},
            current_step=-1,
            next_due_at=datetime.now(UTC),
        )
        db.add(sequence)
        await db.flush()
        created = True
    else:
        sequence.context_json = {**(sequence.context_json or {}), **(context or {})}
        created = False
    return {
        "created": created,
        "status": "scheduled",
        "phone": normalized,
        "contact_id": str(contact.id),
        "sequence_id": str(sequence.id),
    }


async def ensure_contact_sequence(**kwargs) -> dict:
    async with get_db() as db:
        result = await ensure_contact_sequence_in_session(db, **kwargs)
    if result["created"]:
        from app.tasks import run_sms_sequences_task
        run_sms_sequences_task.delay()
    return result
```

Keep `ensure_contact_and_sequence(listing_id, phone)` as a compatibility wrapper
that loads the Listing, requires `campaign_id`, and calls the new primitive.

- [ ] **Step 4: Render from Listing or context and enforce R01**

At the start of `run_due_sms_sequences`, convert `now` to `Europe/Paris` and
return without selecting/sending when outside the configured window:

```python
paris_now = current.astimezone(ZoneInfo("Europe/Paris"))
if not settings.sms_hour_start <= paris_now.hour < settings.sms_hour_end:
    return {"status": "outside_window", "processed": 0, "sent": 0, "stopped": 0}
```

For each sequence, build context as:

```python
render_context = dict(sequence.context_json or {})
if listing is not None:
    render_context.update({"title": listing.title or "votre vehicule", "url": listing.url})
title = render_context.get("title") or "votre demande"
url = render_context.get("url") or ""
body = render_sms_body(template, title=title, url=url).replace("  ", " ").strip()
```

Do not cancel a sequence merely because `listing_id` is null. Continue requiring
Contact and Campaign.

- [ ] **Step 5: Run tests and full SMS regression subset**

Run: `python -m pytest tests/test_sms_sequence.py tests/test_campaign_runner.py tests/test_webhooks.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add app/services/sms_sequence.py app/models.py tests/test_sms_sequence.py
git commit -m "fix: enforce safe generic SMS sequences"
```

---

### Task 7: Deterministic normalizer with bounded AI fallback

**Files:**
- Create: `app/services/apify_normalizer.py`
- Modify: `app/boundaries.py`
- Create: `tests/test_apify_normalizer.py`

- [ ] **Step 1: Write table-driven normalizer tests**

```python
# tests/test_apify_normalizer.py
import pytest

from app.services.apify_normalizer import normalize_apify_item


@pytest.mark.parametrize(
    ("payload", "phone", "title"),
    [
        ({"phone": "06 12 34 56 78", "title": "Clio"}, "+33612345678", "Clio"),
        (
            {"seller": {"contactNumber": "+33 7 11 22 33 44"}, "vehicle": {"name": "208"}},
            "+33711223344",
            "208",
        ),
        (
            {"description": "Vendeur joignable au 06 98 76 54 32", "url": "https://example.test/a"},
            "+33698765432",
            None,
        ),
    ],
)
def test_normalizer_recognizes_nested_and_text_values(payload, phone, title):
    result = normalize_apify_item(payload, schema=None, profile=None)
    assert result.phone_e164 == phone
    assert result.title == title


def test_normalizer_flags_equal_phone_candidates():
    result = normalize_apify_item(
        {"phone1": "0612345678", "phone2": "0698765432"},
        schema=None,
        profile=None,
    )
    assert result.status == "exception"
    assert result.error_code == "ambiguous_phone"
```

- [ ] **Step 2: Run tests and verify missing module**

Run: `python -m pytest tests/test_apify_normalizer.py -q`

Expected: FAIL importing `apify_normalizer`.

- [ ] **Step 3: Implement canonical model, flattening, aliases, and scoring**

```python
class NormalizedApifyLead(BaseModel):
    source_platform: str = "other"
    source_item_id: str | None = None
    url: str | None = None
    title: str | None = None
    description: str | None = None
    phone_e164: str | None = None
    price: int | None = None
    mileage: int | None = None
    location: str | None = None
    brand: str | None = None
    model: str | None = None
    year: int | None = None
    seller_type: str | None = None
    confidence: float = 0.0
    status: Literal["actionable", "non_actionable", "rejected", "exception"]
    error_code: str | None = None
    evidence: dict[str, str] = Field(default_factory=dict)
```

Implement pure functions `flatten_payload`, `schema_fingerprint`,
`collect_candidates`, `score_phone_candidate`, `infer_source_platform` and
`normalize_apify_item`. Priority weights must place schema-described contact
fields above aliases, and aliases above free text. If two top phone candidates
differ by less than 10 score points, return `ambiguous_phone`.

- [ ] **Step 4: Add an optional structured AI boundary**

Add only this frontiere to `app/boundaries.py`:

```python
async def infer_apify_lead_fields(
    payload: dict, candidate_paths: list[str]
) -> dict:
    """Return JSON-only field paths; never initiate an external action."""
    client = AsyncAnthropic()
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        temperature=0,
        system=(
            "Return one JSON object whose values are paths from candidate_paths. "
            "Allowed keys: phone,title,url,description,price,mileage,location."
        ),
        messages=[{
            "role": "user",
            "content": json.dumps(
                {"candidate_paths": candidate_paths, "payload": payload},
                ensure_ascii=False,
            )[:12000],
        }],
    )
    result = json.loads(response.content[0].text)
    return {
        key: path
        for key, path in result.items()
        if isinstance(path, str) and path in candidate_paths
    }
```

Call it from an async wrapper `normalize_apify_item_with_fallback` only when
`settings.apify_ai_fallback_enabled` is true, deterministic extraction found no
unique phone, and the payload contains at least one possible French phone. Pass
only bounded textual fields, validate the returned paths against the original
payload, then rerun deterministic validation. AI cannot directly provide the
final phone value.

- [ ] **Step 5: Add fuzz-style invariants and run tests**

Add tests asserting that arbitrary nesting never raises, no candidate invents a
value absent from the payload, and an invalid phone never becomes actionable.

Run: `python -m pytest tests/test_apify_normalizer.py -q`

Expected: all tests pass.

Run: `python -m ruff check app/services/apify_normalizer.py app/boundaries.py tests/test_apify_normalizer.py`

Expected: exit code 0.

- [ ] **Step 6: Commit**

```bash
git add app/services/apify_normalizer.py app/boundaries.py tests/test_apify_normalizer.py
git commit -m "feat: normalize heterogeneous Apify leads"
```

---

### Task 8: Run orchestration, webhook, and reconciliation

**Files:**
- Create: `app/services/apify_runs.py`
- Create: `app/webhooks/apify.py`
- Modify: `app/main.py`
- Modify: `app/tasks.py`
- Create: `tests/test_apify_webhook.py`
- Create: `tests/test_apify_runs.py`

- [ ] **Step 1: Write failing webhook idempotency tests**

```python
# tests/test_apify_webhook.py
from unittest.mock import patch

import pytest


@pytest.mark.integration
async def test_duplicate_apify_webhook_dispatches_one_import(
    client, existing_apify_account
):
    payload = {
        "eventType": "ACTOR.RUN.SUCCEEDED",
        "resource": {"id": "run-123", "status": "SUCCEEDED", "defaultDatasetId": "ds-1"},
    }
    headers = {"Authorization": "Bearer test-apify-webhook-secret"}

    with patch("app.tasks.import_apify_run_task.delay") as dispatch:
        first = await client.post(
            f"/webhooks/apify/{existing_apify_account.id}", json=payload, headers=headers
        )
        second = await client.post(
            f"/webhooks/apify/{existing_apify_account.id}", json=payload, headers=headers
        )

    assert first.status_code == 202
    assert second.status_code == 202
    dispatch.assert_called_once()
```

- [ ] **Step 2: Run tests and verify route failure**

Run: `python -m pytest tests/test_apify_webhook.py tests/test_apify_runs.py -q`

Expected: FAIL because the webhook and run service are absent.

- [ ] **Step 3: Implement run creation and status synchronization**

Implement `launch_binding(binding_id, trigger)`,
`sync_remote_run(account_id, remote)`, `get_due_binding_ids(now=None)`,
`get_or_sync_remote_run(account_id, remote_run_id)`, `reconcile_runs()` and
`replay_run(run_id)`. Each function returns the Pydantic
output or a dictionary of integer counters, never an ORM row with encrypted
relationships.

Lock each binding with `SELECT FOR UPDATE SKIP LOCKED`, advance
`next_run_at` before the external call, and restore it with a bounded error when
the start call fails. `replay_run` reuses the same `ApifyRun`; it never creates a
new provider run.

- [ ] **Step 4: Implement the fast authenticated webhook**

The route must compare a per-account bearer secret in constant time, upsert the
run by `(account_id, apify_run_id)`, store the webhook event key, respond 202 and
dispatch only after commit:

```python
router = APIRouter(prefix="/webhooks/apify", tags=["apify-webhook"])


@router.post("/{account_id}", status_code=202)
async def receive_apify_webhook(
    account_id: UUID,
    payload: ApifyWebhookPayload,
    authorization: Annotated[str | None, Header()] = None,
):
    queued = await accept_webhook(account_id, payload, authorization)
    if queued:
        import_apify_run_task.delay(str(account_id), payload.resource.id)
    return {"accepted": True}
```

Never fetch a Dataset inside the request.

Add the task symbol used by the webhook now so the route is independently
testable; import the ingestion service inside the task because Task 9 creates it:

```python
@celery_app.task(name="app.tasks.import_apify_run_task", bind=True, max_retries=3)
def import_apify_run_task(self, account_id: str, remote_run_id: str):
    from uuid import UUID
    import httpx
    from app.services.apify_ingestion import import_remote_run
    try:
        return _run(import_remote_run(UUID(account_id), remote_run_id))
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
```

- [ ] **Step 5: Mount the webhook without the generic Control Tower dependency**

In `app/main.py`, import `app.webhooks.apify` under an unambiguous alias and add:

```python
app.include_router(apify_webhook.router)
```

Authentication remains inside the route because Apify cannot send the generic
SMSTools webhook header.

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/test_apify_webhook.py tests/test_apify_runs.py -q`

Expected: all available integration tests pass.

- [ ] **Step 7: Commit**

```bash
git add app/services/apify_runs.py app/webhooks/apify.py app/main.py app/tasks.py tests/test_apify_webhook.py tests/test_apify_runs.py
git commit -m "feat: orchestrate Apify runs and webhooks"
```

---

### Task 9: Idempotent ingestion and automatic sequence start

**Files:**
- Create: `app/services/apify_ingestion.py`
- Create: `tests/test_apify_ingestion.py`

- [ ] **Step 1: Write failing end-to-end ingestion service tests**

```python
# tests/test_apify_ingestion.py
from unittest.mock import patch

import pytest
from sqlalchemy import func, select

from app.db import get_db
from app.services.apify_ingestion import import_run
from app.tables import ApifyItem, SmsSequence


@pytest.mark.integration
async def test_import_creates_one_sequence_and_classifies_other_items(
    succeeded_apify_run, monkeypatch
):
    rows = [
        {"url": "https://www.leboncoin.fr/ad/1", "title": "Clio", "phone": "0612345678"},
        {"url": "https://www.leboncoin.fr/ad/1", "title": "Clio", "phone": "+33612345678"},
        {"title": "Sans telephone"},
    ]

    async def fake_iter_dataset(token, dataset_id):
        async for row in async_items(rows):
            yield row

    monkeypatch.setattr("app.boundaries.apify_iter_dataset", fake_iter_dataset)

    result = await import_run(succeeded_apify_run.id)

    assert result == {"read": 3, "actionable": 2, "sequences_created": 1, "exceptions": 0}
    async with get_db() as db:
        assert await db.scalar(select(func.count()).select_from(ApifyItem)) == 3
        assert await db.scalar(select(func.count()).select_from(SmsSequence)) == 1


async def async_items(items):
    for index, item in enumerate(items):
        yield index, item
```

- [ ] **Step 2: Run the ingestion tests and verify missing service**

Run: `python -m pytest tests/test_apify_ingestion.py -q`

Expected: FAIL importing `apify_ingestion`.

- [ ] **Step 3: Implement per-item idempotent import**

```python
async def import_run(run_id: UUID) -> dict[str, int]:
    """Import every dataset item; one malformed item cannot abort the run."""
    counters = {"read": 0, "actionable": 0, "sequences_created": 0, "exceptions": 0}
    run, token = await _load_run_and_token(run_id)
    async for index, payload in boundaries.apify_iter_dataset(token, run.dataset_id):
        outcome = await _import_one_item(run_id, index, payload)
        counters["read"] += 1
        counters["actionable"] += int(outcome.status == "actionable")
        counters["sequences_created"] += int(outcome.sequence_created)
        counters["exceptions"] += int(outcome.status == "exception")
    await _finish_run_import(run_id, counters)
    if counters["sequences_created"]:
        from app.tasks import run_sms_sequences_task
        run_sms_sequences_task.delay()
    return counters


async def import_remote_run(account_id: UUID, remote_run_id: str) -> dict[str, int]:
    from app.services.apify_runs import get_or_sync_remote_run
    run_id = await get_or_sync_remote_run(account_id, remote_run_id)
    return await import_run(run_id)
```

For each `(index, payload)`:

1. hash canonical JSON with sorted keys;
2. insert-or-load `ApifyItem` under its unique constraint;
3. normalize with the binding profile;
4. store non-actionable/rejected statuses without exception rows;
5. create `ApifyException` only for grave ambiguity;
6. upsert Listing when URL and listing context are sufficient;
7. call `ensure_contact_sequence_in_session` with campaign, optional Listing and
   normalized context;
8. store links and finish the item.

Use a nested transaction/savepoint per item. Update run counters after each
page-sized batch. Dispatch `run_sms_sequences_task.delay()` once after commit if
at least one sequence was newly created.

- [ ] **Step 4: Add deduplication assertions**

Extend the test to import the same run twice and a second run from another Actor
with the same phone. Assert the item counts are stable for replay and the
sequence count stays one for the campaign.

- [ ] **Step 5: Run focused tests and lint**

Run: `python -m pytest tests/test_apify_ingestion.py tests/test_sms_sequence.py -q`

Expected: all tests pass.

Run: `python -m ruff check app/services/apify_ingestion.py tests/test_apify_ingestion.py`

Expected: exit code 0.

- [ ] **Step 6: Commit**

```bash
git add app/services/apify_ingestion.py tests/test_apify_ingestion.py
git commit -m "feat: ingest Apify leads into SMS sequences"
```

---

### Task 10: Controlled normalization learning loop

**Files:**
- Create: `app/services/apify_learning.py`
- Create: `tests/test_apify_learning.py`

- [ ] **Step 1: Write failing keep/discard/rollback tests**

```python
# tests/test_apify_learning.py
from app.services.apify_learning import compare_profiles


def test_candidate_is_discarded_when_a_stable_phone_changes():
    baseline = [{"item": "1", "phone": "+33612345678", "status": "actionable"}]
    candidate = [{"item": "1", "phone": "+33699999999", "status": "actionable"}]

    decision = compare_profiles(baseline, candidate, minimum_sample_size=1)

    assert decision.status == "discard"
    assert decision.reason == "stable_phone_regression"


def test_candidate_can_keep_safe_new_coverage():
    baseline = [{"item": "1", "phone": None, "status": "non_actionable"}]
    candidate = [
        {
            "item": "1",
            "phone": "+33612345678",
            "status": "actionable",
            "independent_signals": 2,
        }
    ]
    decision = compare_profiles(baseline, candidate, minimum_sample_size=1)
    assert decision.status == "keep"
```

- [ ] **Step 2: Run tests and verify missing module**

Run: `python -m pytest tests/test_apify_learning.py -q`

Expected: FAIL importing `apify_learning`.

- [ ] **Step 3: Implement pure profile comparison**

```python
class ProfileDecision(BaseModel):
    status: Literal["keep", "discard", "crash"]
    reason: str
    metrics: dict[str, float | int]


def compare_profiles(
    baseline: list[dict], candidate: list[dict], *, minimum_sample_size: int
) -> ProfileDecision:
    if len(candidate) < minimum_sample_size:
        return ProfileDecision(
            status="discard",
            reason="insufficient_sample",
            metrics={"sample_size": len(candidate)},
        )
    old = {row["item"]: row for row in baseline}
    changed = sum(
        1
        for row in candidate
        if old.get(row["item"], {}).get("phone")
        and old[row["item"]]["phone"] != row.get("phone")
    )
    if changed:
        return ProfileDecision(
            status="discard",
            reason="stable_phone_regression",
            metrics={"changed_stable_phones": changed},
        )
    unsafe_new = sum(
        1
        for row in candidate
        if not old.get(row["item"], {}).get("phone")
        and row.get("phone")
        and row.get("independent_signals", 0) < 2
    )
    if unsafe_new:
        return ProfileDecision(
            status="discard",
            reason="insufficient_evidence",
            metrics={"unsafe_new_coverage": unsafe_new},
        )
    return ProfileDecision(
        status="keep",
        reason="safe_non_regression",
        metrics={"sample_size": len(candidate)},
    )
```

Hard gates: no changed stable phone, no new blacklist violation, no increased
ambiguity, no duplicate regression and at least two independent signals for new
coverage. Complexity breaks ties: fewer mappings win when metrics are equal.

- [ ] **Step 4: Implement persisted experiments and atomic promotion**

Implement `create_candidate_profile(binding_id)`,
`evaluate_candidate(profile_id)`, `promote_profile(profile_id)` and
`rollback_profile(binding_id, profile_id)`. The create function copies the
active profile into `candidate` state before applying newly inferred mappings;
evaluation persists both metric sets and the decision; promotion and rollback
use row locks on binding and profile.

`evaluate_candidate` replays raw `ApifyItem` rows without calling the sequence
service. `promote_profile` locks the binding and candidate, verifies the stored
decision is `keep`, retires the old profile and swaps `active_profile_id` in one
transaction. No learning path may import or send.

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_apify_learning.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add app/services/apify_learning.py tests/test_apify_learning.py
git commit -m "feat: add controlled Apify learning loop"
```

---

### Task 11: Celery tasks, connector health, and circuit breakers

**Files:**
- Modify: `app/tasks.py`
- Modify: `app/services/connector_monitor.py`
- Modify: `front/components/ConnectorControlPanel.tsx`
- Create: `tests/test_apify_tasks.py`
- Modify: `tests/test_connector_monitor.py`

- [ ] **Step 1: Write failing dispatch and health tests**

```python
# tests/test_apify_tasks.py
from unittest.mock import AsyncMock, patch

from app.tasks import dispatch_due_apify_bindings_task


@patch("app.tasks.launch_apify_binding_task.delay")
@patch("app.services.apify_runs.get_due_binding_ids", new_callable=AsyncMock)
def test_dispatch_queues_each_due_binding(get_due, delay):
    get_due.return_value = ["binding-1", "binding-2"]
    result = dispatch_due_apify_bindings_task()
    assert result["dispatched"] == 2
    assert delay.call_count == 2
```

Add connector tests asserting `apify` is `disabled` with zero accounts, `ok`
when at least one account probe succeeds, and `degraded` when some accounts fail.

- [ ] **Step 2: Run tests and verify missing task**

Run: `python -m pytest tests/test_apify_tasks.py tests/test_connector_monitor.py -q`

Expected: FAIL importing `dispatch_due_apify_bindings_task`.

- [ ] **Step 3: Add routed Celery tasks**

Add an `apify` queue and beat entries:

```python
"dispatch-due-apify-bindings": {
    "task": "app.tasks.dispatch_due_apify_bindings_task",
    "schedule": 60.0,
},
"reconcile-apify-runs": {
    "task": "app.tasks.reconcile_apify_runs_task",
    "schedule": float(settings.apify_reconcile_minutes * 60),
},
"evaluate-apify-profiles": {
    "task": "app.tasks.evaluate_apify_profiles_task",
    "schedule": 3600.0,
},
```

Implement named tasks for binding launch, run import, reconciliation and profile
evaluation. Network/rate-limit failures retry with `60 * 2**retries` plus small
jitter, max three. Validation errors do not retry. Persist every terminal error.

- [ ] **Step 4: Add binding circuit breakers**

After an import, compute the last 100 items. Suspend only the binding when any
condition holds: ambiguous phone rate above 10%, duplicate anomaly above 20%,
or schema fingerprint changed with zero actionable items. Record an
`ApifyException` with category `binding_suspended` and leave other bindings live.

- [ ] **Step 5: Add aggregate connector status**

`connector_monitor` must query account states without decrypting all tokens for
the dashboard read. A manual probe decrypts and validates each active account
through `boundaries.apify_validate_token`, then stores only latency/status/error.
Add `['apify', 'Apify']` to the connector card list and link the card to `/apify`.

- [ ] **Step 6: Run focused tests**

Run: `python -m pytest tests/test_apify_tasks.py tests/test_connector_monitor.py -q`

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add app/tasks.py app/services/connector_monitor.py front/components/ConnectorControlPanel.tsx tests/test_apify_tasks.py tests/test_connector_monitor.py
git commit -m "feat: schedule and monitor Apify automation"
```

---

### Task 12: Protected Apify API

**Files:**
- Create: `app/api/apify.py`
- Modify: `app/security.py`
- Modify: `app/main.py`
- Create: `tests/test_apify_api.py`

- [ ] **Step 1: Write API permission and redaction tests**

```python
# tests/test_apify_api.py
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.integration
async def test_viewer_cannot_add_apify_account(client):
    response = await client.post(
        "/api/v1/apify/accounts",
        json={"label": "Principal", "token": "apify_api_secret"},
        headers={"X-Operator-Role": "viewer"},
    )
    assert response.status_code == 403


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
```

- [ ] **Step 2: Run tests and verify 404/missing route**

Run: `python -m pytest tests/test_apify_api.py -q`

Expected: FAIL because `/api/v1/apify` is not mounted.

- [ ] **Step 3: Add a reusable role checker without refactoring unrelated routes**

Add to `app/security.py`:

```python
def require_control_role(role: str, minimum: str) -> None:
    aliases = {"operateur": "operator", "manager": "operator", "administrateur": "admin"}
    normalized = aliases.get(role, role)
    rank = {"viewer": 0, "operator": 1, "admin": 2}
    if rank.get(normalized, -1) < rank[minimum]:
        raise HTTPException(403, detail={"code": "INSUFFICIENT_ROLE"})
```

Do not rewrite the existing operations authorization in this task.

- [ ] **Step 4: Implement route contracts**

Expose:

```text
GET/POST                  /api/v1/apify/accounts
PATCH/DELETE              /api/v1/apify/accounts/{id}
POST                      /api/v1/apify/accounts/{id}/probe
POST                      /api/v1/apify/accounts/{id}/catalog/sync
GET/POST                  /api/v1/apify/bindings
PATCH                      /api/v1/apify/bindings/{id}
POST                      /api/v1/apify/bindings/{id}/run
GET                       /api/v1/apify/runs
POST                      /api/v1/apify/runs/{id}/replay
GET                       /api/v1/apify/items
GET                       /api/v1/apify/items/{id}
GET                       /api/v1/apify/learning
POST                      /api/v1/apify/profiles/{id}/rollback
GET                       /api/v1/apify/summary
```

Admin: account/binding mutation and rollback. Operator: run/replay. Viewer:
read-only. Bound pagination to 100 items per page. Mask phones unless the caller
is operator/admin. Never return encrypted columns or full exception payloads.

- [ ] **Step 5: Mount the protected router**

In `app/main.py`:

```python
app.include_router(apify_api.router, dependencies=protected)
```

- [ ] **Step 6: Run API and security regressions**

Run: `python -m pytest tests/test_apify_api.py tests/test_security_regressions.py -q`

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add app/api/apify.py app/security.py app/main.py tests/test_apify_api.py
git commit -m "feat: expose protected Apify operations API"
```

---

### Task 13: Dashboard API proxy and account/binding panels

**Files:**
- Create: `front/lib/apify-api.ts`
- Create: `front/app/api/apify/[...path]/route.ts`
- Create: `front/app/apify/page.tsx`
- Create: `front/components/ApifyControlCenter.tsx`
- Create: `front/components/ApifyAccountsPanel.tsx`
- Create: `front/components/ApifyBindingsPanel.tsx`
- Modify: `front/components/NavLinks.tsx`
- Modify: `front/tests/handlers.ts`
- Create: `front/components/ApifyControlCenter.test.tsx`

- [ ] **Step 1: Add failing component tests**

```tsx
// front/components/ApifyControlCenter.test.tsx
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ApifyControlCenter } from './ApifyControlCenter'
import { mockApifyDashboard } from '@/tests/handlers'

describe('ApifyControlCenter', () => {
  it('never renders a saved token and can submit a new account', async () => {
    render(<ApifyControlCenter initialData={mockApifyDashboard} />)
    expect(screen.queryByText('apify_api_secret')).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Libelle du compte'), { target: { value: 'Secondaire' } })
    fireEvent.change(screen.getByLabelText('Jeton Apify'), { target: { value: 'apify_api_new' } })
    fireEvent.click(screen.getByRole('button', { name: 'Connecter le compte' }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Compte connecte'))
  })

  it('requires campaign and scheduling authority before enabling a binding', () => {
    render(<ApifyControlCenter initialData={mockApifyDashboard} />)
    fireEvent.click(screen.getByRole('button', { name: 'Activer Example Actor' }))
    expect(screen.getByText('Selectionnez une campagne active')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run frontend tests and verify missing component**

Run: `npm test -- --run components/ApifyControlCenter.test.tsx`

Working directory: `front`

Expected: FAIL resolving `./ApifyControlCenter`.

- [ ] **Step 3: Define frontend types and server reads**

`front/lib/apify-api.ts` must define masked account, catalog, binding, run, item,
profile, exception and summary types. Add a server-only `fetchApifyDashboard()`
that uses `NEXT_PUBLIC_API_URL`, `CONTROL_TOWER_TOKEN`, `cache: 'no-store'` and
never logs response bodies.

- [ ] **Step 4: Implement one generic authenticated BFF proxy**

In the catch-all route, support GET/POST/PATCH/DELETE and forward through:

```ts
async function proxy(request: NextRequest, segments: string[]) {
  const target = new URL(`/api/v1/apify/${segments.join('/')}`, API_URL)
  target.search = request.nextUrl.search
  const body = request.method === 'GET' || request.method === 'DELETE'
    ? undefined
    : await request.text()
  const response = await fetch(target, {
    method: request.method,
    headers: { ...controlApiHeaders(request), 'X-Control-Tower-Token': CONTROL_TOKEN },
    body,
    cache: 'no-store',
  })
  return new NextResponse(await response.text(), {
    status: response.status,
    headers: { 'Content-Type': response.headers.get('Content-Type') ?? 'application/json' },
  })
}
```

Reject missing `CONTROL_TOWER_TOKEN` with 503. Do not cache mutation responses.

- [ ] **Step 5: Implement page, accounts, and bindings**

The server page loads initial data. The client control center provides accessible
tabs. Account token uses `type="password"`, `autoComplete="off"`, clears after
submit, and is never placed back into state from a response. Binding controls
show resource type, account, campaign, sector, scheduling authority, next run,
webhook and profile state. Activation remains disabled until backend-required
fields are present.

- [ ] **Step 6: Add navigation and MSW handlers**

Add `{ href: '/apify', label: 'Apify', compact: 'Apify', icon: Bot }` under
Systeme. Add handlers for summary, accounts, bindings and mutations; fixtures
contain only `token_masked`.

- [ ] **Step 7: Run focused frontend tests and build**

Run: `npm test -- --run components/ApifyControlCenter.test.tsx`

Working directory: `front`

Expected: all tests pass.

Run: `npm run build`

Working directory: `front`

Expected: Next.js build succeeds.

- [ ] **Step 8: Commit**

```bash
git add front/lib/apify-api.ts front/app/api/apify front/app/apify front/components/ApifyControlCenter.tsx front/components/ApifyAccountsPanel.tsx front/components/ApifyBindingsPanel.tsx front/components/NavLinks.tsx front/tests/handlers.ts front/components/ApifyControlCenter.test.tsx
git commit -m "feat: add Apify account and Actor dashboard"
```

---

### Task 14: Runs, results, learning, and exception dashboard panels

**Files:**
- Create: `front/components/ApifyRunsPanel.tsx`
- Create: `front/components/ApifyResultsPanel.tsx`
- Create: `front/components/ApifyLearningPanel.tsx`
- Modify: `front/components/ApifyControlCenter.tsx`
- Modify: `front/components/ApifyControlCenter.test.tsx`

- [ ] **Step 1: Add failing tests for masking, replay, and rollback**

```tsx
it('masks phones for viewers and exposes run replay status', async () => {
  render(<ApifyControlCenter initialData={mockApifyDashboard} />)
  fireEvent.click(screen.getByRole('tab', { name: 'Resultats' }))
  expect(screen.getByText('+33 ** ** ** 67 8')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('tab', { name: 'Runs' }))
  fireEvent.click(screen.getByRole('button', { name: 'Rejouer import run-1' }))
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Import relance'))
})

it('shows keep and discard experiments without enabling SMS actions', () => {
  render(<ApifyControlCenter initialData={mockApifyDashboard} />)
  fireEvent.click(screen.getByRole('tab', { name: 'Apprentissage' }))
  expect(screen.getByText('discard')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /envoyer sms/i })).not.toBeInTheDocument()
})
```

- [ ] **Step 2: Run the tests and verify missing panels**

Run: `npm test -- --run components/ApifyControlCenter.test.tsx`

Working directory: `front`

Expected: FAIL because the tabs/panels are absent.

- [ ] **Step 3: Implement runs and result panels**

Runs show provider status, duration, Dataset ID, cost, counters, error summary and
replay. Results provide Actor/run/status/date filters, pagination, masked phone,
canonical fields, links to Contact/Listing/Sequence, and a disclosure for raw
versus normalized JSON. Render JSON with `<pre>` as escaped text; never use
`dangerouslySetInnerHTML`.

- [ ] **Step 4: Implement learning and exceptions panel**

Show active/candidate/retired profiles, schema fingerprint, baseline/candidate
metrics, keep/discard/crash decisions, circuit-breaker state and rollback for
admins. Exceptions show category and masked evidence only. There is no per-item
button to begin an SMS sequence.

- [ ] **Step 5: Verify accessibility and frontend regressions**

Run: `npm test -- --run components/ApifyControlCenter.test.tsx tests/components.test.tsx`

Working directory: `front`

Expected: all tests pass.

Run: `npm run build`

Working directory: `front`

Expected: build succeeds without hydration or type errors.

- [ ] **Step 6: Commit**

```bash
git add front/components/ApifyRunsPanel.tsx front/components/ApifyResultsPanel.tsx front/components/ApifyLearningPanel.tsx front/components/ApifyControlCenter.tsx front/components/ApifyControlCenter.test.tsx
git commit -m "feat: expose Apify runs leads and learning"
```

---

### Task 15: End-to-end safety proof, documentation, and rollout gates

**Files:**
- Create: `tests/test_apify_e2e.py`
- Modify: `tests/test_security_regressions.py`
- Modify: `docs/CONTROL_TOWER_OPERATIONS.md`
- Modify: `docs/GUIDE_COMPLET_UTILISATION.md`
- Modify: `docs/Plan_Implementation_Modules.html`

- [ ] **Step 1: Write the complete E2E safety test**

```python
# tests/test_apify_e2e.py
from datetime import UTC, datetime

import pytest


@pytest.mark.integration
async def test_apify_dataset_to_sms_is_idempotent_and_hour_safe(
    monkeypatch, mock_send_sms, succeeded_apify_run
):
    from sqlalchemy import func, select
    from app.db import get_db
    from app.services.apify_ingestion import import_run
    from app.services.sms_sequence import run_due_sms_sequences
    from app.tables import ApifyException, ApifyItem, SmsSequence

    rows = [
        {"seller": {"phone": "0612345678"}, "title": "Clio", "url": "https://www.leboncoin.fr/ad/1"},
        {"seller": {"phone": "+33612345678"}, "title": "Clio copie", "url": "https://www.leboncoin.fr/ad/2"},
        {"description": "aucun contact"},
        {"phoneA": "0611111111", "phoneB": "0622222222"},
    ]

    async def fake_iter_dataset(token, dataset_id):
        for index, item in enumerate(rows):
            yield index, item

    monkeypatch.setattr("app.boundaries.apify_iter_dataset", fake_iter_dataset)

    await import_run(succeeded_apify_run.id)
    await run_due_sms_sequences(now=datetime(2026, 7, 16, 3, 0, tzinfo=UTC))
    assert mock_send_sms.await_count == 0

    await import_run(succeeded_apify_run.id)
    await run_due_sms_sequences(now=datetime(2026, 7, 16, 9, 0, tzinfo=UTC))
    assert mock_send_sms.await_count == 1

    async with get_db() as db:
        assert await db.scalar(select(func.count()).select_from(SmsSequence)) == 1
        assert await db.scalar(select(func.count()).select_from(ApifyException)) == 1
        assert await db.scalar(select(func.count()).select_from(ApifyItem)) == 4
```

Use test helpers that call real services and DB, mocking only boundaries.

- [ ] **Step 2: Add security regression assertions**

Test that token and encrypted input never appear in account/catalog/run/item API
responses, audit events, captured logs or error messages. Test forged webhook,
wrong account secret, viewer mutation and raw HTML strings in payloads.

- [ ] **Step 3: Run the complete backend verification**

Run: `python -m pytest -q`

Expected: full backend suite passes; integration tests may skip only when the
documented test PostgreSQL/Redis services are absent.

Run: `python -m ruff check app tests`

Expected: exit code 0.

- [ ] **Step 4: Run the complete frontend verification**

Run: `npm test -- --run`

Working directory: `front`

Expected: all Vitest tests pass.

Run: `npm run build`

Working directory: `front`

Expected: production build succeeds.

- [ ] **Step 5: Update operational documentation with exact gates**

Document:

```text
Gate 1: compte connecte, catalog sync, aucun run automatique
Gate 2: import historique, sequences desactivees
Gate 3: profil fantome, zero changement de telephone stable
Gate 4: un Actor, campagne de test, quota par SIM reduit
Gate 5: verification des doublons, STOP et 08h-20h
Gate 6: extension progressive puis apprentissage automatique
```

Add commands for Fernet key generation, token rotation, webhook probe, binding
suspension, import replay and profile rollback. Correct the obsolete daily 06:00
comment and state that the five-minute dispatcher selects only due sectors.

- [ ] **Step 6: Verify the migration on a clean database and a copy with existing sequences**

Run: `python -m alembic downgrade p6g7h8i9j0k1 && python -m alembic upgrade head`

Expected: downgrade/upgrade complete in the disposable integration database.

Run the same `upgrade head` against a disposable copy containing duplicate
contact/campaign sequences and verify the oldest sequence remains.

- [ ] **Step 7: Commit**

```bash
git add tests/test_apify_e2e.py tests/test_security_regressions.py docs/CONTROL_TOWER_OPERATIONS.md docs/GUIDE_COMPLET_UTILISATION.md docs/Plan_Implementation_Modules.html
git commit -m "test: verify Apify automation safety"
```

---

## Final acceptance checklist

- [ ] Multiple Apify accounts can coexist without cross-workspace access.
- [ ] Tokens and Actor inputs are encrypted, write-only and absent from logs.
- [ ] Actors and Tasks are discovered, bound, launched and reconciled.
- [ ] Dataset pagination and webhook replay are idempotent.
- [ ] Heterogeneous fields normalize without inventing values.
- [ ] Ambiguous recipients stop at the binding exception boundary.
- [ ] One contact receives at most one sequence per campaign.
- [ ] Generic leads work without a fabricated Listing.
- [ ] SMS never sends outside 08:00-20:00 Europe/Paris.
- [ ] Experiments never call import or SMS paths.
- [ ] Dashboard covers accounts, bindings, runs, results, learning and exceptions.
- [ ] Existing scraping, campaigns, webhooks and dashboard tests remain green.
- [ ] Rollout gates are documented and the first deployment starts with automation disabled.
