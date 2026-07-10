# Control Tower Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the trustworthy read-side foundation for the control tower: correct iproxy routing, persistent operational state, connector monitoring, actionable dashboard data, and responsive UI surfaces.

**Architecture:** Keep FastAPI, SQLAlchemy, Alembic, Celery, PostgreSQL, Redis, Next.js, and Radix UI. Provider calls remain isolated in `app/boundaries.py`; a focused monitor translates read-only probes into persisted connector states. The dashboard reads persisted operational data and never performs slow provider calls during page rendering.

**Tech Stack:** Python 3.14, FastAPI, Pydantic, SQLAlchemy 2, Alembic, PostgreSQL, Redis, Celery, pytest, Next.js 15, React 19, TypeScript, Radix UI, Vitest.

---

## Delivery Boundary

This plan intentionally does not expose destructive dashboard commands. Authentication and command authorization are implemented in the next plan together so that no unauthenticated control endpoint exists temporarily.

This plan delivers:

- correct documented iproxy connection paths;
- operational persistence tables;
- scheduled, read-only connector monitoring;
- truthful distinction between configured, verified, degraded, and down;
- workflow/message counters backed by tables;
- action-required dashboard alerts;
- responsive connector and workflow panels;
- focused backend and frontend tests.

## File Map

### Create

- `migrations/versions/e5a1c7d9f3b2_add_control_tower_foundation.py`: operational tables and indexes.
- `app/services/connector_monitor.py`: read-only probes, error classification, and persistence.
- `tests/test_connector_monitor.py`: connector probe and persistence behavior.
- `tests/test_dashboard.py`: dashboard action derivation and response contract.
- `front/components/ControlTowerOverview.tsx`: action, workflow, and connector panels.
- `front/components/ControlTowerOverview.test.tsx`: component states and responsive content.
- `front/app/globals.css`: responsive application shell.

### Modify

- `.env.example`: documented iproxy connection id.
- `app/config.py`: `iproxy_connection_id` setting and strict group validation.
- `app/boundaries.py`: documented iproxy URLs.
- `app/models.py`: operational enums and dashboard output contracts.
- `app/tables.py`: four operational ORM tables.
- `app/schema_sync.py`: idempotent compatibility creation for deployed instances.
- `app/tasks.py`: connector refresh task and beat schedule.
- `app/api/dashboard.py`: persisted workflow/message/connector metrics and actions.
- `front/lib/api.ts`: typed control-tower response.
- `front/components/DashboardRealtime.tsx`: compose the new overview without rewriting balance/call behavior.
- `front/app/layout.tsx`: use responsive shell classes.
- `front/components/NavLinks.tsx`: desktop sidebar and compact mobile navigation.
- `front/lib/dashboard-state.test.ts`: expanded dashboard fixture.
- `tests/test_boundaries.py`: iproxy request contract.

## Task 1: Correct the iproxy API Contract

**Files:**
- Modify: `.env.example`
- Modify: `app/config.py`
- Modify: `app/boundaries.py`
- Test: `tests/test_boundaries.py`
- Test: `tests/test_config_validation.py`

- [ ] **Step 1: Add failing configuration tests**

Append to `tests/test_config_validation.py`:

```python
def test_strict_validation_requires_complete_iproxy_configuration():
    from pydantic import ValidationError

    from app.config import Settings

    with pytest.raises(ValidationError, match="iproxy.online configuration is incomplete"):
        Settings(
            secret_key="local-secret",
            strict_startup_validation=True,
            iproxy_api_key="api-key",
            iproxy_connection_id="connection-1",
            iproxy_proxy_id="",
        )
```

- [ ] **Step 2: Add failing boundary tests for documented paths**

Append to `tests/test_boundaries.py`:

```python
@pytest.mark.asyncio
async def test_get_4g_proxy_uses_connection_scoped_endpoint():
    from app import boundaries

    response = Mock()
    response.json.return_value = {
        "proxy_accesses": [{
            "id": "proxy-7",
            "auth": {"login": "user", "password": "pass"},
            "listen_service": "http",
            "hostname": "proxy.example",
            "port": 9000,
        }]
    }
    response.raise_for_status.return_value = None

    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = False
    client.get = AsyncMock(return_value=response)

    settings = SimpleNamespace(
        iproxy_api_key="api-key",
        iproxy_connection_id="connection-3",
        iproxy_proxy_id="proxy-7",
    )
    with (
        patch("app.boundaries.httpx.AsyncClient", return_value=client),
        patch.object(boundaries, "settings", settings),
    ):
        proxy = await boundaries.get_4g_proxy()

    client.get.assert_awaited_once_with(
        "https://iproxy.online/api/console/v1/connection/connection-3/proxy-access",
        headers={"Authorization": "Bearer api-key"},
    )
    assert proxy.url == "http://user:pass@proxy.example:9000"


@pytest.mark.asyncio
async def test_rotate_4g_ip_uses_connection_scoped_endpoint():
    from app import boundaries

    response = Mock(status_code=200)
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = False
    client.post = AsyncMock(return_value=response)

    settings = SimpleNamespace(
        iproxy_api_key="api-key",
        iproxy_connection_id="connection-3",
    )
    with (
        patch("app.boundaries.httpx.AsyncClient", return_value=client),
        patch.object(boundaries, "settings", settings),
    ):
        assert await boundaries.rotate_4g_ip() is True

    client.post.assert_awaited_once_with(
        "https://iproxy.online/api/console/v1/connection/connection-3/command-push",
        headers={"Authorization": "Bearer api-key"},
        json={"action": "changeip"},
    )


@pytest.mark.asyncio
async def test_get_4g_proxy_rejects_missing_connection_id():
    from app import boundaries

    settings = SimpleNamespace(
        iproxy_api_key="api-key",
        iproxy_connection_id="",
        iproxy_proxy_id="proxy-7",
    )
    with patch.object(boundaries, "settings", settings):
        with pytest.raises(ValueError, match="IPROXY_CONNECTION_ID"):
            await boundaries.get_4g_proxy()
```

Also add `from types import SimpleNamespace` to the test imports.

- [ ] **Step 3: Run the focused tests and verify RED**

Run:

```powershell
$env:TMP='C:\tmp'; $env:TEMP='C:\tmp'; python -m pytest tests/test_config_validation.py::test_strict_validation_requires_complete_iproxy_configuration tests/test_boundaries.py::test_get_4g_proxy_uses_connection_scoped_endpoint tests/test_boundaries.py::test_rotate_4g_ip_uses_connection_scoped_endpoint tests/test_boundaries.py::test_get_4g_proxy_rejects_missing_connection_id -q -o cache_dir=C:\tmp\pytest-cache-auto-bot
```

Expected: failures because `iproxy_connection_id` and the connection-scoped URLs do not exist.

- [ ] **Step 4: Implement the setting and URLs**

Add to `Settings` in `app/config.py`:

```python
iproxy_connection_id: str = ""
```

Change the strict iproxy validation group to:

```python
self._require_all_or_none(
    "iproxy.online",
    self.iproxy_api_key,
    self.iproxy_connection_id,
    self.iproxy_proxy_id,
)
```

Add to `.env.example` below `IPROXY_API_KEY`:

```dotenv
IPROXY_CONNECTION_ID=
```

Change `get_4g_proxy()` in `app/boundaries.py` to call:

```python
if not settings.iproxy_connection_id:
    raise ValueError("IPROXY_CONNECTION_ID is required")

f"{_IPROXY_BASE}/connection/{settings.iproxy_connection_id}/proxy-access"
```

Change `rotate_4g_ip()` to call:

```python
f"{_IPROXY_BASE}/connection/{settings.iproxy_connection_id}/command-push"
```

- [ ] **Step 5: Run focused tests and verify GREEN**

Run the command from Step 3.

Expected: `4 passed`.

- [ ] **Step 6: Commit Task 1**

```powershell
git add .env.example app/config.py app/boundaries.py tests/test_boundaries.py tests/test_config_validation.py
git commit -m "fix: use documented iproxy connection routes"
```

## Task 2: Add Operational Persistence

**Files:**
- Modify: `app/models.py`
- Modify: `app/tables.py`
- Create: `migrations/versions/e5a1c7d9f3b2_add_control_tower_foundation.py`
- Modify: `app/schema_sync.py`
- Test: `tests/test_dashboard.py`

- [ ] **Step 1: Write the failing metadata test**

Create `tests/test_dashboard.py`:

```python
from app.db import Base


def test_control_tower_tables_are_registered():
    assert {
        "workflow_runs",
        "connector_status",
        "audit_events",
        "lbc_message_log",
    }.issubset(Base.metadata.tables)
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
$env:TMP='C:\tmp'; $env:TEMP='C:\tmp'; python -m pytest tests/test_dashboard.py::test_control_tower_tables_are_registered -q -o cache_dir=C:\tmp\pytest-cache-auto-bot
```

Expected: FAIL listing the four missing tables.

- [ ] **Step 3: Add operational enums**

Add to `app/models.py` after `CampaignStatus`:

```python
class WorkflowStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ConnectorState(StrEnum):
    DISABLED = "disabled"
    UNVERIFIED = "unverified"
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"
    MISCONFIGURED = "misconfigured"


class LbcMessageDirection(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class LbcMessageStatus(StrEnum):
    QUEUED = "queued"
    SENT = "sent"
    RECEIVED = "received"
    FAILED = "failed"
    SKIPPED = "skipped"
```

- [ ] **Step 4: Add the ORM tables**

Import `JSON` and `ForeignKey` from SQLAlchemy in `app/tables.py`, import the four enums, then append:

```python
class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    workflow_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(50))
    target_id: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(
        Enum(WorkflowStatus, name="workflow_status"),
        default=WorkflowStatus.PENDING,
        nullable=False,
    )
    progress_current: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_total: Mapped[int | None] = mapped_column(Integer)
    batch_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    batch_size: Mapped[int | None] = mapped_column(Integer)
    celery_task_id: Mapped[str | None] = mapped_column(String(100))
    checkpoint: Mapped[dict | None] = mapped_column(JSON)
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    last_error: Mapped[str | None] = mapped_column(Text)
    initiated_by: Mapped[str | None] = mapped_column(String(100))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ConnectorStatus(Base):
    __tablename__ = "connector_status"

    name: Mapped[str] = mapped_column(String(50), primary_key=True)
    status: Mapped[str] = mapped_column(
        Enum(
            ConnectorState,
            name="connector_state",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    configured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_summary: Mapped[str | None] = mapped_column(String(300))
    details: Mapped[dict | None] = mapped_column(JSON)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    action: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(50))
    target_id: Mapped[str | None] = mapped_column(String(100))
    idempotency_key: Mapped[str | None] = mapped_column(String(100), index=True)
    input_summary: Mapped[dict | None] = mapped_column(JSON)
    result_status: Mapped[str] = mapped_column(String(30), nullable=False)
    workflow_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_runs.id"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LbcMessageLog(Base):
    __tablename__ = "lbc_message_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_key: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    listing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("listings.id"), index=True
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("platform_accounts.id"), index=True
    )
    direction: Mapped[str] = mapped_column(
        Enum(
            LbcMessageDirection,
            name="lbc_message_direction",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Enum(
            LbcMessageStatus,
            name="lbc_message_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    content_hash: Mapped[str | None] = mapped_column(String(64))
    preview: Mapped[str | None] = mapped_column(String(160))
    phone_extracted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 5: Add the Alembic migration**

Create `migrations/versions/e5a1c7d9f3b2_add_control_tower_foundation.py`:

```python
"""add control tower foundation

Revision ID: e5a1c7d9f3b2
Revises: d4f7c2a9b8e1
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e5a1c7d9f3b2"
down_revision = "d4f7c2a9b8e1"
branch_labels = None
depends_on = None

workflow_status = sa.Enum(
    "PENDING", "RUNNING", "PAUSED", "COMPLETED", "FAILED", "CANCELLED",
    name="workflow_status",
)
connector_state = sa.Enum(
    "disabled", "unverified", "ok", "degraded", "down", "misconfigured",
    name="connector_state",
)
lbc_message_direction = sa.Enum("inbound", "outbound", name="lbc_message_direction")
lbc_message_status = sa.Enum(
    "queued", "sent", "received", "failed", "skipped",
    name="lbc_message_status",
)


def upgrade() -> None:
    op.create_table(
        "workflow_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("idempotency_key", sa.String(100), nullable=False, unique=True),
        sa.Column("workflow_type", sa.String(50), nullable=False),
        sa.Column("target_type", sa.String(50)),
        sa.Column("target_id", sa.String(100)),
        sa.Column("status", workflow_status, nullable=False),
        sa.Column("progress_current", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_total", sa.Integer()),
        sa.Column("batch_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("batch_size", sa.Integer()),
        sa.Column("celery_task_id", sa.String(100)),
        sa.Column("checkpoint", sa.JSON()),
        sa.Column("last_error_code", sa.String(80)),
        sa.Column("last_error", sa.Text()),
        sa.Column("initiated_by", sa.String(100)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_workflow_runs_workflow_type", "workflow_runs", ["workflow_type"])

    op.create_table(
        "connector_status",
        sa.Column("name", sa.String(50), primary_key=True),
        sa.Column("status", connector_state, nullable=False),
        sa.Column("configured", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_summary", sa.String(300)),
        sa.Column("details", sa.JSON()),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("target_type", sa.String(50)),
        sa.Column("target_id", sa.String(100)),
        sa.Column("idempotency_key", sa.String(100)),
        sa.Column("input_summary", sa.JSON()),
        sa.Column("result_status", sa.String(30), nullable=False),
        sa.Column(
            "workflow_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_runs.id"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_idempotency_key", "audit_events", ["idempotency_key"])
    op.create_index("ix_audit_events_workflow_run_id", "audit_events", ["workflow_run_id"])

    op.create_table(
        "lbc_message_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("external_key", sa.String(150), nullable=False, unique=True),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("listings.id")),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("platform_accounts.id"),
        ),
        sa.Column("direction", lbc_message_direction, nullable=False),
        sa.Column("status", lbc_message_status, nullable=False),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("preview", sa.String(160)),
        sa.Column("phone_extracted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_code", sa.String(80)),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_lbc_message_log_listing_id", "lbc_message_log", ["listing_id"])
    op.create_index("ix_lbc_message_log_account_id", "lbc_message_log", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_lbc_message_log_account_id", table_name="lbc_message_log")
    op.drop_index("ix_lbc_message_log_listing_id", table_name="lbc_message_log")
    op.drop_table("lbc_message_log")
    op.drop_index("ix_audit_events_workflow_run_id", table_name="audit_events")
    op.drop_index("ix_audit_events_idempotency_key", table_name="audit_events")
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("connector_status")
    op.drop_index("ix_workflow_runs_workflow_type", table_name="workflow_runs")
    op.drop_table("workflow_runs")
    lbc_message_status.drop(op.get_bind(), checkfirst=True)
    lbc_message_direction.drop(op.get_bind(), checkfirst=True)
    connector_state.drop(op.get_bind(), checkfirst=True)
    workflow_status.drop(op.get_bind(), checkfirst=True)
```

- [ ] **Step 6: Add runtime compatibility DDL**

Use SQLAlchemy metadata for missing tables while retaining the existing column compatibility statements. Change `ensure_runtime_schema()` in `app/schema_sync.py` to:

```python
async def ensure_runtime_schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for statement in _DDL:
            await conn.execute(text(statement))
```

Add `from app.db import Base, engine` and remove the old engine-only import.

- [ ] **Step 7: Run metadata and migration checks**

Run:

```powershell
$env:TMP='C:\tmp'; $env:TEMP='C:\tmp'; python -m pytest tests/test_dashboard.py::test_control_tower_tables_are_registered -q -o cache_dir=C:\tmp\pytest-cache-auto-bot
python -m alembic upgrade head --sql > C:\tmp\control-tower-migration.sql
```

Expected: metadata test passes and Alembic emits SQL without import or revision errors.

- [ ] **Step 8: Commit Task 2**

```powershell
git add app/models.py app/tables.py app/schema_sync.py migrations/versions/e5a1c7d9f3b2_add_control_tower_foundation.py tests/test_dashboard.py
git commit -m "feat: add control tower operational storage"
```

## Task 3: Persist Connector Monitoring

**Files:**
- Create: `app/services/connector_monitor.py`
- Modify: `app/tasks.py`
- Create: `tests/test_connector_monitor.py`

- [ ] **Step 1: Write failing classification tests**

Create `tests/test_connector_monitor.py`:

```python
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.models import ConnectorState


@pytest.mark.asyncio
async def test_probe_iproxy_does_not_retry_authentication_failure():
    from app.services.connector_monitor import probe_iproxy

    request = httpx.Request("GET", "https://iproxy.online")
    response = httpx.Response(401, request=request)
    error = httpx.HTTPStatusError("unauthorized", request=request, response=response)

    settings = SimpleNamespace(
        iproxy_api_key="api-key",
        iproxy_connection_id="connection-1",
        iproxy_proxy_id="proxy-1",
    )
    with (
        patch("app.services.connector_monitor.get_settings", return_value=settings),
        patch("app.services.connector_monitor.boundaries.get_4g_proxy", new_callable=AsyncMock) as probe,
    ):
        probe.side_effect = error
        result = await probe_iproxy()

    assert result.status == ConnectorState.MISCONFIGURED
    assert result.error_code == "HTTP_401"
    assert result.configured is True
    probe.assert_awaited_once()


@pytest.mark.asyncio
async def test_probe_smstools_reports_success_latency():
    from app.services.connector_monitor import probe_smstools

    settings = SimpleNamespace(smstools_api_key="api-key")
    with (
        patch("app.services.connector_monitor.get_settings", return_value=settings),
        patch(
            "app.services.connector_monitor.boundaries.get_sim_list",
            new_callable=AsyncMock,
            return_value=[{"id": "sim-1", "status": "active"}],
        ),
    ):
        result = await probe_smstools()

    assert result.status == ConnectorState.OK
    assert result.configured is True
    assert result.details == {"active_sims": 1}
    assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_refresh_connector_statuses_persists_each_probe():
    from app.models import ConnectorProbeResult
    from app.services.connector_monitor import refresh_connector_statuses

    class _Context:
        async def __aenter__(self):
            return db

        async def __aexit__(self, exc_type, exc, tb):
            return False

    db = AsyncMock()
    smstools = ConnectorProbeResult(
        name="smstools", status=ConnectorState.OK, configured=True
    )
    iproxy = ConnectorProbeResult(
        name="iproxy", status=ConnectorState.MISCONFIGURED, configured=True,
        error_code="HTTP_401",
    )

    with (
        patch("app.services.connector_monitor.probe_smstools", new_callable=AsyncMock, return_value=smstools),
        patch("app.services.connector_monitor.probe_iproxy", new_callable=AsyncMock, return_value=iproxy),
        patch("app.services.connector_monitor.get_db", return_value=_Context()),
    ):
        results = await refresh_connector_statuses()

    assert results == [smstools, iproxy]
    assert db.execute.await_count == 2
```

- [ ] **Step 2: Run and verify RED**

Run:

```powershell
$env:TMP='C:\tmp'; $env:TEMP='C:\tmp'; python -m pytest tests/test_connector_monitor.py -q -o cache_dir=C:\tmp\pytest-cache-auto-bot
```

Expected: import failure because the monitor module does not exist.

- [ ] **Step 3: Add the connector result contract**

Add to `app/models.py`:

```python
class ConnectorProbeResult(BaseModel):
    name: str
    status: ConnectorState
    configured: bool
    latency_ms: int | None = None
    error_code: str | None = None
    error_summary: str | None = None
    details: dict[str, Any] | None = None
```

- [ ] **Step 4: Implement read-only probes and persistence**

Create `app/services/connector_monitor.py` with:

```python
import time
from datetime import UTC, datetime

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app import boundaries
from app.config import get_settings
from app.db import get_db
from app.models import ConnectorProbeResult, ConnectorState
from app.tables import ConnectorStatus


def _elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def _failure(name: str, configured: bool, started: float, exc: Exception) -> ConnectorProbeResult:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code in (401, 403):
        state = ConnectorState.MISCONFIGURED
    elif status_code == 429:
        state = ConnectorState.DEGRADED
    else:
        state = ConnectorState.DOWN
    return ConnectorProbeResult(
        name=name,
        status=state,
        configured=configured,
        latency_ms=_elapsed_ms(started),
        error_code=f"HTTP_{status_code}" if status_code else type(exc).__name__,
        error_summary=str(exc)[:300],
    )


async def probe_iproxy() -> ConnectorProbeResult:
    settings = get_settings()
    configured = bool(
        settings.iproxy_api_key
        and settings.iproxy_connection_id
        and settings.iproxy_proxy_id
    )
    if not configured:
        return ConnectorProbeResult(
            name="iproxy", status=ConnectorState.DISABLED, configured=False
        )
    started = time.perf_counter()
    try:
        await boundaries.get_4g_proxy()
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        return _failure("iproxy", True, started, exc)
    return ConnectorProbeResult(
        name="iproxy",
        status=ConnectorState.OK,
        configured=True,
        latency_ms=_elapsed_ms(started),
    )


async def probe_smstools() -> ConnectorProbeResult:
    settings = get_settings()
    if not settings.smstools_api_key:
        return ConnectorProbeResult(
            name="smstools", status=ConnectorState.DISABLED, configured=False
        )
    started = time.perf_counter()
    try:
        sims = await boundaries.get_sim_list()
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        return _failure("smstools", True, started, exc)
    active = sum(1 for sim in sims if sim.get("status") == "active")
    return ConnectorProbeResult(
        name="smstools",
        status=ConnectorState.OK,
        configured=True,
        latency_ms=_elapsed_ms(started),
        details={"active_sims": active},
    )


async def refresh_connector_statuses() -> list[ConnectorProbeResult]:
    results = [await probe_smstools(), await probe_iproxy()]
    now = datetime.now(UTC)
    async with get_db() as db:
        for result in results:
            await db.execute(
                pg_insert(ConnectorStatus)
                .values(
                    name=result.name,
                    status=result.status,
                    configured=result.configured,
                    latency_ms=result.latency_ms,
                    last_success_at=now if result.status == ConnectorState.OK else None,
                    last_checked_at=now,
                    error_code=result.error_code,
                    error_summary=result.error_summary,
                    details=result.details,
                )
                .on_conflict_do_update(
                    index_elements=["name"],
                    set_={
                        "status": result.status,
                        "configured": result.configured,
                        "latency_ms": result.latency_ms,
                        "last_success_at": (
                            now if result.status == ConnectorState.OK
                            else ConnectorStatus.last_success_at
                        ),
                        "last_checked_at": now,
                        "error_code": result.error_code,
                        "error_summary": result.error_summary,
                        "details": result.details,
                    },
                )
            )
    return results
```

- [ ] **Step 5: Add the Celery refresh task**

Add to `beat_schedule` in `app/tasks.py`:

```python
"refresh-connector-status": {
    "task": "app.tasks.refresh_connector_status_task",
    "schedule": 60.0,
},
```

Add the task:

```python
@celery_app.task(name="app.tasks.refresh_connector_status_task")
def refresh_connector_status_task():
    from app.services.connector_monitor import refresh_connector_statuses

    results = _run(refresh_connector_statuses())
    return [result.model_dump(mode="json") for result in results]
```

- [ ] **Step 6: Run focused tests and verify GREEN**

Run:

```powershell
$env:TMP='C:\tmp'; $env:TEMP='C:\tmp'; python -m pytest tests/test_connector_monitor.py -q -o cache_dir=C:\tmp\pytest-cache-auto-bot
```

Expected: `3 passed`.

- [ ] **Step 7: Commit Task 3**

```powershell
git add app/models.py app/services/connector_monitor.py app/tasks.py tests/test_connector_monitor.py
git commit -m "feat: persist connector health probes"
```

## Task 4: Expand the Dashboard Read Contract

**Files:**
- Modify: `app/models.py`
- Modify: `app/api/dashboard.py`
- Test: `tests/test_dashboard.py`

- [ ] **Step 1: Write failing action derivation tests**

Append to `tests/test_dashboard.py`:

```python
from datetime import UTC, datetime
from types import SimpleNamespace

from app.models import ConnectorState


def test_dashboard_actions_prioritize_connector_failures_and_account_shortage():
    from app.api.dashboard import build_action_items

    connectors = [
        SimpleNamespace(
            name="iproxy",
            status=ConnectorState.MISCONFIGURED,
            error_code="HTTP_401",
            error_summary="unauthorized",
            last_checked_at=datetime.now(UTC),
        )
    ]

    actions = build_action_items(connectors, accounts_active=2, accounts_minimum=3)

    assert [action.code for action in actions] == [
        "connector.iproxy.HTTP_401",
        "accounts.pool_below_minimum",
    ]
    assert actions[0].severity == "critical"
```

- [ ] **Step 2: Run and verify RED**

Run:

```powershell
$env:TMP='C:\tmp'; $env:TEMP='C:\tmp'; python -m pytest tests/test_dashboard.py::test_dashboard_actions_prioritize_connector_failures_and_account_shortage -q -o cache_dir=C:\tmp\pytest-cache-auto-bot
```

Expected: import failure for `build_action_items`.

- [ ] **Step 3: Add dashboard output contracts**

Add to `app/models.py`:

```python
class DashboardConnector(BaseModel):
    name: str
    status: ConnectorState
    configured: bool
    latency_ms: int | None = None
    last_success_at: datetime | None = None
    last_checked_at: datetime | None = None
    error_code: str | None = None
    error_summary: str | None = None
    details: dict[str, Any] | None = None


class DashboardActionItem(BaseModel):
    code: str
    severity: str
    title: str
    detail: str
    target: str


class DashboardWorkflow(BaseModel):
    id: UUID
    workflow_type: str
    status: WorkflowStatus
    progress_current: int
    progress_total: int | None
    batch_number: int
    batch_size: int | None
    last_error: str | None
    updated_at: datetime
```

Extend `DashboardStats` with:

```python
lbc_messages_sent_total: int = 0
lbc_messages_sent_today: int = 0
lbc_messages_received_total: int = 0
lbc_messages_received_today: int = 0
phones_extracted_total: int = 0
phones_extracted_today: int = 0
connectors: list[DashboardConnector] = []
actions_required: list[DashboardActionItem] = []
workflows: list[DashboardWorkflow] = []
generated_at: datetime
```

Use `Field(default_factory=list)` instead of literal list defaults in production code.

- [ ] **Step 4: Implement deterministic action derivation**

Add to `app/api/dashboard.py`:

```python
def build_action_items(
    connectors: list[ConnectorStatus],
    *,
    accounts_active: int,
    accounts_minimum: int,
) -> list[DashboardActionItem]:
    actions: list[DashboardActionItem] = []
    for connector in connectors:
        if connector.status in (
            ConnectorState.DOWN,
            ConnectorState.MISCONFIGURED,
        ):
            severity = "critical"
        elif connector.status == ConnectorState.DEGRADED:
            severity = "warning"
        else:
            continue
        code = connector.error_code or connector.status
        actions.append(DashboardActionItem(
            code=f"connector.{connector.name}.{code}",
            severity=severity,
            title=f"Connecteur {connector.name} indisponible",
            detail=connector.error_summary or "Verification requise",
            target=connector.name,
        ))

    if accounts_active < accounts_minimum:
        actions.append(DashboardActionItem(
            code="accounts.pool_below_minimum",
            severity="warning",
            title="Pool de comptes insuffisant",
            detail=f"{accounts_active} actifs pour un minimum de {accounts_minimum}",
            target="accounts",
        ))
    return sorted(actions, key=lambda item: item.severity != "critical")
```

- [ ] **Step 5: Query persisted message, connector, and workflow state**

Import the operational models/tables, then add these queries inside the existing `async with get_db()` block in `get_dashboard()`:

```python
lbc_messages_sent_total = (await db.execute(
    select(func.count()).select_from(LbcMessageLog).where(
        LbcMessageLog.direction == LbcMessageDirection.OUTBOUND,
        LbcMessageLog.status == LbcMessageStatus.SENT,
    )
)).scalar() or 0
lbc_messages_sent_today = (await db.execute(
    select(func.count()).select_from(LbcMessageLog).where(
        LbcMessageLog.direction == LbcMessageDirection.OUTBOUND,
        LbcMessageLog.status == LbcMessageStatus.SENT,
        LbcMessageLog.created_at >= today_start,
    )
)).scalar() or 0
lbc_messages_received_total = (await db.execute(
    select(func.count()).select_from(LbcMessageLog).where(
        LbcMessageLog.direction == LbcMessageDirection.INBOUND,
        LbcMessageLog.status == LbcMessageStatus.RECEIVED,
    )
)).scalar() or 0
lbc_messages_received_today = (await db.execute(
    select(func.count()).select_from(LbcMessageLog).where(
        LbcMessageLog.direction == LbcMessageDirection.INBOUND,
        LbcMessageLog.status == LbcMessageStatus.RECEIVED,
        LbcMessageLog.created_at >= today_start,
    )
)).scalar() or 0
phones_extracted_total = (await db.execute(
    select(func.count()).select_from(LbcMessageLog).where(
        LbcMessageLog.phone_extracted.is_(True)
    )
)).scalar() or 0
phones_extracted_today = (await db.execute(
    select(func.count()).select_from(LbcMessageLog).where(
        LbcMessageLog.phone_extracted.is_(True),
        LbcMessageLog.created_at >= today_start,
    )
)).scalar() or 0

connector_rows = (
    await db.execute(select(ConnectorStatus).order_by(ConnectorStatus.name))
).scalars().all()
workflow_rows = (
    await db.execute(
        select(WorkflowRun)
        .where(WorkflowRun.status.in_([
            WorkflowStatus.PENDING,
            WorkflowStatus.RUNNING,
            WorkflowStatus.PAUSED,
            WorkflowStatus.FAILED,
        ]))
        .order_by(WorkflowRun.updated_at.desc())
        .limit(10)
    )
).scalars().all()

connectors = [DashboardConnector.model_validate(row) for row in connector_rows]
workflows = [DashboardWorkflow.model_validate(row) for row in workflow_rows]
actions_required = build_action_items(
    connector_rows,
    accounts_active=accounts_active,
    accounts_minimum=get_settings().lbc_accounts_min_active,
)
```

Add `model_config = {"from_attributes": True}` to `DashboardConnector` and `DashboardWorkflow`.

Pass these exact values to `DashboardStats(...)`:

```python
lbc_messages_sent_total=lbc_messages_sent_total,
lbc_messages_sent_today=lbc_messages_sent_today,
lbc_messages_received_total=lbc_messages_received_total,
lbc_messages_received_today=lbc_messages_received_today,
phones_extracted_total=phones_extracted_total,
phones_extracted_today=phones_extracted_today,
connectors=connectors,
actions_required=actions_required,
workflows=workflows,
generated_at=datetime.now(UTC),
```

Do not call provider APIs from this endpoint.

- [ ] **Step 6: Run dashboard tests**

Run:

```powershell
$env:TMP='C:\tmp'; $env:TEMP='C:\tmp'; python -m pytest tests/test_dashboard.py tests/test_health.py -q -o cache_dir=C:\tmp\pytest-cache-auto-bot
```

Expected: all dashboard and health tests pass.

- [ ] **Step 7: Commit Task 4**

```powershell
git add app/models.py app/api/dashboard.py tests/test_dashboard.py
git commit -m "feat: expose control tower dashboard state"
```

## Task 5: Render the Control Tower Overview

**Files:**
- Modify: `front/lib/api.ts`
- Create: `front/components/ControlTowerOverview.tsx`
- Create: `front/components/ControlTowerOverview.test.tsx`
- Modify: `front/components/DashboardRealtime.tsx`
- Modify: `front/lib/dashboard-state.test.ts`

- [ ] **Step 1: Add the failing component test**

Create `front/components/ControlTowerOverview.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { Theme } from '@radix-ui/themes'
import { describe, expect, it } from 'vitest'

import { ControlTowerOverview } from '@/components/ControlTowerOverview'
import type { DashboardStats } from '@/lib/api'

const stats = {
  listings_total: 1284,
  listings_today: 42,
  sms_sent_total: 207,
  sms_sent_today: 31,
  calls_total: 8,
  calls_today: 2,
  sms_received_total: 23,
  sms_received_today: 3,
  accounts_active: 2,
  accounts_total: 3,
  campaigns_running: 1,
  balances: [],
  lbc_messages_sent_total: 318,
  lbc_messages_sent_today: 18,
  lbc_messages_received_total: 105,
  lbc_messages_received_today: 7,
  phones_extracted_total: 94,
  phones_extracted_today: 5,
  connectors: [{
    name: 'iproxy',
    status: 'misconfigured',
    configured: true,
    latency_ms: 120,
    last_success_at: null,
    last_checked_at: '2026-07-10T12:00:00Z',
    error_code: 'HTTP_401',
    error_summary: 'Authentification refusee',
    details: null,
  }],
  actions_required: [{
    code: 'connector.iproxy.HTTP_401',
    severity: 'critical',
    title: 'Connecteur iproxy indisponible',
    detail: 'Authentification refusee',
    target: 'iproxy',
  }],
  workflows: [],
  generated_at: '2026-07-10T12:00:00Z',
} satisfies DashboardStats

describe('ControlTowerOverview', () => {
  it('shows messaging metrics and required actions', () => {
    render(<Theme><ControlTowerOverview stats={stats} /></Theme>)

    expect(screen.getByText('Messages LBC envoyes')).toBeTruthy()
    expect(screen.getByText('Numeros extraits')).toBeTruthy()
    expect(screen.getByText('Connecteur iproxy indisponible')).toBeTruthy()
    expect(screen.getByText('HTTP_401')).toBeTruthy()
  })
})
```

- [ ] **Step 2: Run and verify RED**

Run from `front`:

```powershell
npm test -- ControlTowerOverview.test.tsx
```

Expected: module-not-found failure for `ControlTowerOverview` and missing `DashboardStats` fields.

- [ ] **Step 3: Extend TypeScript contracts**

Add to `front/lib/api.ts` before `DashboardStats`:

```ts
export type ConnectorState =
  | 'disabled'
  | 'unverified'
  | 'ok'
  | 'degraded'
  | 'down'
  | 'misconfigured'

export type DashboardConnector = {
  name: string
  status: ConnectorState
  configured: boolean
  latency_ms: number | null
  last_success_at: string | null
  last_checked_at: string | null
  error_code: string | null
  error_summary: string | null
  details: Record<string, unknown> | null
}

export type DashboardActionItem = {
  code: string
  severity: 'critical' | 'warning' | 'info'
  title: string
  detail: string
  target: string
}

export type DashboardWorkflow = {
  id: string
  workflow_type: string
  status: 'PENDING' | 'RUNNING' | 'PAUSED' | 'COMPLETED' | 'FAILED' | 'CANCELLED'
  progress_current: number
  progress_total: number | null
  batch_number: number
  batch_size: number | null
  last_error: string | null
  updated_at: string
}
```

Add to `DashboardStats`:

```ts
lbc_messages_sent_total: number
lbc_messages_sent_today: number
lbc_messages_received_total: number
lbc_messages_received_today: number
phones_extracted_total: number
phones_extracted_today: number
connectors: DashboardConnector[]
actions_required: DashboardActionItem[]
workflows: DashboardWorkflow[]
generated_at: string
```

- [ ] **Step 4: Implement the overview component**

Create `front/components/ControlTowerOverview.tsx`:

```tsx
'use client'

import { Badge, Box, Flex, Heading, Text } from '@radix-ui/themes'

import type { ConnectorState, DashboardStats } from '@/lib/api'

const STATUS_COLOR: Record<ConnectorState, string> = {
  disabled: '#6b7280',
  unverified: '#6b7280',
  ok: '#18794e',
  degraded: '#ad5700',
  down: '#b42318',
  misconfigured: '#b42318',
}

export function ControlTowerOverview({ stats }: { stats: DashboardStats }) {
  const metrics = [
    ['Annonces collectees', stats.listings_total, stats.listings_today],
    ['Messages LBC envoyes', stats.lbc_messages_sent_total, stats.lbc_messages_sent_today],
    ['Messages LBC recus', stats.lbc_messages_received_total, stats.lbc_messages_received_today],
    ['Numeros extraits', stats.phones_extracted_total, stats.phones_extracted_today],
    ['SMS envoyes', stats.sms_sent_total, stats.sms_sent_today],
    ['Appels recus', stats.calls_total, stats.calls_today],
  ] as const

  return (
    <Box mb="5">
      {stats.actions_required.length > 0 && (
        <Box
          mb="4"
          p="3"
          style={{
            border: '1px solid var(--orange-6)',
            borderLeft: '4px solid var(--orange-9)',
            background: 'var(--orange-2)',
          }}
        >
          <Heading size="3" mb="2">Actions requises</Heading>
          <Flex direction="column" gap="2">
            {stats.actions_required.map((action) => (
              <Flex key={action.code} justify="between" gap="3" wrap="wrap">
                <Box style={{ minWidth: 0 }}>
                  <Text size="2" weight="bold" as="div">{action.title}</Text>
                  <Text size="1" color="gray" as="div" style={{ overflowWrap: 'anywhere' }}>
                    {action.detail}
                  </Text>
                </Box>
                <Badge color={action.severity === 'critical' ? 'red' : 'orange'}>
                  {action.code.split('.').at(-1)}
                </Badge>
              </Flex>
            ))}
          </Flex>
        </Box>
      )}

      <Text size="3" weight="bold" as="div" mb="2">Activite</Text>
      <Box
        mb="5"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
          gap: 12,
        }}
      >
        {metrics.map(([label, total, today]) => (
          <Box key={label} p="3" style={{ border: '1px solid var(--gray-5)', minWidth: 0 }}>
            <Text size="2" color="gray" as="div">{label}</Text>
            <Text size="7" weight="bold" as="div">{total}</Text>
            <Text size="1" color="gray" as="div">+{today} aujourd&apos;hui</Text>
          </Box>
        ))}
      </Box>

      <Text size="3" weight="bold" as="div" mb="2">Workflows</Text>
      <Box mb="5" style={{ borderTop: '1px solid var(--gray-5)' }}>
        {stats.workflows.length === 0 && (
          <Text size="2" color="gray" as="div" py="3">Aucun workflow actif</Text>
        )}
        {stats.workflows.map((workflow) => (
          <Flex
            key={workflow.id}
            justify="between"
            gap="3"
            py="3"
            wrap="wrap"
            style={{ borderBottom: '1px solid var(--gray-5)' }}
          >
            <Box style={{ minWidth: 180 }}>
              <Text size="2" weight="bold" as="div">{workflow.workflow_type}</Text>
              <Text size="1" color="gray" as="div">
                Lot {workflow.batch_number} - {workflow.progress_current}
                {workflow.progress_total !== null ? ` / ${workflow.progress_total}` : ''}
              </Text>
            </Box>
            <Badge color={workflow.status === 'FAILED' ? 'red' : workflow.status === 'PAUSED' ? 'orange' : 'blue'}>
              {workflow.status}
            </Badge>
            {workflow.last_error && (
              <Text size="1" color="red" style={{ overflowWrap: 'anywhere', maxWidth: 360 }}>
                {workflow.last_error}
              </Text>
            )}
          </Flex>
        ))}
      </Box>

      <Text size="3" weight="bold" as="div" mb="2">Connecteurs et infrastructure</Text>
      <Box
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: 12,
        }}
      >
        {stats.connectors.map((connector) => (
          <Box key={connector.name} p="3" style={{ border: '1px solid var(--gray-5)', minWidth: 0 }}>
            <Flex justify="between" gap="2" align="center">
              <Text size="2" weight="bold">{connector.name}</Text>
              <Text size="1" weight="bold" style={{ color: STATUS_COLOR[connector.status] }}>
                {connector.status}
              </Text>
            </Flex>
            <Text size="1" color="gray" as="div" mt="1">
              {connector.latency_ms === null ? 'Latence inconnue' : `${connector.latency_ms} ms`}
            </Text>
            {connector.error_code && (
              <Text size="1" color="red" as="div" mt="1" style={{ overflowWrap: 'anywhere' }}>
                {connector.error_code}
              </Text>
            )}
          </Box>
        ))}
      </Box>
    </Box>
  )
}
```

- [ ] **Step 5: Make the application shell responsive**

Create `front/app/globals.css`:

```css
* { box-sizing: border-box; }
body { margin: 0; }
.app-shell { display: flex; min-height: 100vh; }
.app-main { flex: 1; min-width: 0; padding: 24px; overflow-y: auto; }
.desktop-nav {
  display: block;
  width: 220px;
  min-height: 100vh;
  flex-shrink: 0;
  padding: 24px 16px;
  border-right: 1px solid var(--gray-4);
}
.mobile-nav { display: none; }

@media (max-width: 700px) {
  .app-shell { display: block; }
  .app-main { padding: 16px; }
  .desktop-nav { display: none; }
  .mobile-nav {
    position: sticky;
    top: 0;
    z-index: 10;
    display: flex;
    gap: 4px;
    overflow-x: auto;
    padding: 10px 12px;
    border-bottom: 1px solid var(--gray-4);
    background: var(--color-background);
  }
}
```

Import it in `front/app/layout.tsx` after the Radix stylesheet:

```tsx
import './globals.css'
```

Replace the shell markup in `front/app/layout.tsx` with:

```tsx
<div className="app-shell">
  <NavLinks />
  <main className="app-main">{children}</main>
</div>
```

Replace `front/components/NavLinks.tsx` with:

```tsx
'use client'

import { Flex, Text } from '@radix-ui/themes'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

const NAV_ITEMS = [
  { href: '/dashboard', label: 'Tableau de bord', compact: 'Dashboard' },
  { href: '/listings', label: 'Annonces', compact: 'Annonces' },
  { href: '/campaigns', label: 'Campagnes', compact: 'Campagnes' },
  { href: '/accounts', label: 'Comptes LBC', compact: 'Comptes' },
  { href: '/analyzer', label: 'Analyste prix', compact: 'Analyse' },
]

function NavItem({ href, label }: { href: string; label: string }) {
  const pathname = usePathname()
  const active = pathname === href
  return (
    <Link
      href={href}
      style={{
        display: 'block',
        flexShrink: 0,
        padding: '8px 10px',
        borderRadius: 6,
        textDecoration: 'none',
        whiteSpace: 'nowrap',
        backgroundColor: active ? 'var(--blue-3)' : 'transparent',
        color: active ? 'var(--blue-11)' : 'var(--gray-11)',
        fontSize: 14,
        fontWeight: active ? 600 : 400,
      }}
    >
      {label}
    </Link>
  )
}

export function NavLinks() {
  return (
    <>
      <nav className="desktop-nav" aria-label="Navigation principale">
        <Text size="4" weight="bold" as="div" mb="6" color="blue">
          AutoTransfert
        </Text>
        <Flex direction="column" gap="1">
          {NAV_ITEMS.map((item) => (
            <NavItem key={item.href} href={item.href} label={item.label} />
          ))}
        </Flex>
      </nav>
      <nav className="mobile-nav" aria-label="Navigation mobile">
        {NAV_ITEMS.map((item) => (
          <NavItem key={item.href} href={item.href} label={item.compact} />
        ))}
      </nav>
    </>
  )
}
```

- [ ] **Step 6: Compose it into DashboardRealtime**

In `DashboardRealtime.tsx`, replace the existing `Activite` stat-card block with:

```tsx
{stats && <ControlTowerOverview stats={stats} />}
```

Keep credit/balance cards, incoming-call behavior, and accounts/campaign cards unchanged. Keep the API-unavailable state visible.

- [ ] **Step 7: Update existing dashboard fixture**

Add zero/default values for the new fields to `baseStats` in `front/lib/dashboard-state.test.ts`.

- [ ] **Step 8: Run frontend tests and verify GREEN**

Run from `front`:

```powershell
npm test
npm run lint
npm run build
```

Expected: all Vitest tests pass, ESLint reports no errors, and Next build exits 0.

- [ ] **Step 9: Commit Task 5**

```powershell
git add front/app/globals.css front/app/layout.tsx front/lib/api.ts front/lib/dashboard-state.test.ts front/components/NavLinks.tsx front/components/ControlTowerOverview.tsx front/components/ControlTowerOverview.test.tsx front/components/DashboardRealtime.tsx
git commit -m "feat: render control tower overview"
```

## Task 6: Full Verification and Visual QA

**Files:**
- No production file changes expected.

- [ ] **Step 1: Run backend verification**

```powershell
$env:TMP='C:\tmp'; $env:TEMP='C:\tmp'; python -m pytest -q -o cache_dir=C:\tmp\pytest-cache-auto-bot
python -m ruff check app tests
```

Expected: all non-integration tests pass, integration tests skip only when their declared external dependency is unavailable, and Ruff reports `All checks passed!`.

- [ ] **Step 2: Run frontend verification**

From `front`:

```powershell
npm test
npm run lint
npm run build
```

Expected: all commands exit 0 without warnings caused by the changed code.

- [ ] **Step 3: Run migration verification**

```powershell
python -m alembic heads
python -m alembic upgrade head --sql > C:\tmp\control-tower-foundation.sql
```

Expected: one head at `e5a1c7d9f3b2` and valid SQL output.

- [ ] **Step 4: Start development services for visual QA**

Verify ports 8000 and 3000 are free, then start both processes hidden:

```powershell
Get-NetTCPConnection -LocalPort 8000,3000 -State Listen -ErrorAction SilentlyContinue
Start-Process -FilePath python -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory $PWD -WindowStyle Hidden
Start-Process -FilePath npm.cmd -ArgumentList 'run','dev' -WorkingDirectory (Join-Path $PWD 'front') -WindowStyle Hidden
```

Expected: the port check returns no listeners before startup; `/health` responds on port 8000 and `/dashboard` responds on port 3000 after startup.

- [ ] **Step 5: Capture desktop and mobile screenshots**

Install the pinned Playwright CLI browser if absent, then capture both viewports:

```powershell
npx --yes playwright@1.55.0 install chromium
npx --yes playwright@1.55.0 screenshot --viewport-size="1440,1000" --wait-for-timeout=1500 http://localhost:3000/dashboard C:\tmp\control-tower-desktop.png
npx --yes playwright@1.55.0 screenshot --viewport-size="390,844" --wait-for-timeout=1500 http://localhost:3000/dashboard C:\tmp\control-tower-mobile.png
```

Inspect `C:\tmp\control-tower-desktop.png` and `C:\tmp\control-tower-mobile.png` at original resolution. Verify:

- no overlap or horizontal page overflow;
- all six metrics remain readable;
- action-required content appears before metrics;
- connector error codes wrap safely;
- existing balance and account sections still render;
- API unavailable state remains understandable.

- [ ] **Step 6: Inspect the final diff**

```powershell
git diff --check
git status --short
git diff --stat
```

Expected: no whitespace errors and no unrelated files staged.

- [ ] **Step 7: Commit visual-only corrections if needed**

If visual QA required corrections, commit only those files:

```powershell
git add front/components/ControlTowerOverview.tsx front/components/DashboardRealtime.tsx
git commit -m "fix: polish control tower responsive layout"
```

If no correction was needed, do not create an empty commit.

## Completion Report

Report:

- the original connector and dashboard problems;
- the confirmed iproxy root cause;
- files changed;
- migrations added;
- backend and frontend test counts;
- lint and build results;
- screenshot viewports checked;
- current live connector states without exposing credentials;
- remaining blockers for authenticated commands, Browser Use Cloud expansion, messaging synchronization, Camoufox, and Obscura.
