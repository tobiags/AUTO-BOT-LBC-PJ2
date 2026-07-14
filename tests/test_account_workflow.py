from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import AccountStatus, WorkflowStatus


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reconcile_marks_stale_pending_account_creation_failed():
    from app.services.account_control import reconcile_account_creation_workflows

    workflow = SimpleNamespace(
        workflow_type="account.create",
        status=WorkflowStatus.PENDING,
        started_at=None,
        created_at=datetime.now(UTC) - timedelta(minutes=20),
        checkpoint=None,
        last_error_code=None,
        last_error=None,
        finished_at=None,
    )
    db = AsyncMock()
    db.scalars = AsyncMock(return_value=SimpleNamespace(all=lambda: [workflow]))
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=db)
    context.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.account_control.get_db", return_value=context):
        result = await reconcile_account_creation_workflows()

    assert result == {"reconciled": 1}
    assert workflow.status == WorkflowStatus.FAILED
    assert workflow.last_error_code == "WORKER_TIMEOUT"
    assert workflow.checkpoint == {"stage": "reconciled_timeout"}
    assert workflow.finished_at is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_failed_account_creation_quarantines_placeholder(
    mock_buy_number,
):
    from app.services.account_creation import AccountCreationError, create_lbc_account

    holder = {}

    async def get_account(_model, _account_id):
        return holder.get("account")

    db = AsyncMock()
    db.add = MagicMock(side_effect=lambda account: holder.update(account=account))
    db.get = AsyncMock(side_effect=get_account)
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=db)
    context.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.services.account_creation.get_db", return_value=context),
        patch(
            "app.services.account_creation._create_with_browser_use",
            new_callable=AsyncMock,
        ) as browser,
        patch("app.boundaries.generate_email", return_value="failed@tmp.fr"),
    ):
        browser.side_effect = AccountCreationError("OTP unavailable")
        with pytest.raises(AccountCreationError, match="OTP unavailable"):
            await create_lbc_account(mode="B")
    assert holder["account"].status == AccountStatus.QUARANTAINE
