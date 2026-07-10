"""Tests campaign_runner - fenetre horaire, blacklist, quotas."""
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from zoneinfo import ZoneInfo

import pytest

PARIS = ZoneInfo("Europe/Paris")


def test_sms_within_window():
    from app.services.campaign_runner import is_within_sms_window

    with patch("app.services.campaign_runner.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 6, 18, 10, 0, tzinfo=PARIS)
        assert is_within_sms_window() is True


def test_sms_outside_window_evening():
    from app.services.campaign_runner import is_within_sms_window

    with patch("app.services.campaign_runner.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 6, 18, 21, 0, tzinfo=PARIS)
        assert is_within_sms_window() is False


def test_sms_outside_window_morning():
    from app.services.campaign_runner import is_within_sms_window

    with patch("app.services.campaign_runner.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 6, 18, 7, 30, tzinfo=PARIS)
        assert is_within_sms_window() is False


def test_next_sms_window_start_before_opening():
    from app.services.campaign_runner import next_sms_window_start

    current = datetime(2026, 6, 18, 7, 30, tzinfo=PARIS)
    assert next_sms_window_start(current) == datetime(2026, 6, 18, 8, 0, tzinfo=PARIS)


def test_next_sms_window_start_after_closing():
    from app.services.campaign_runner import next_sms_window_start

    current = datetime(2026, 6, 18, 21, 15, tzinfo=PARIS)
    assert next_sms_window_start(current) == datetime(2026, 6, 19, 8, 0, tzinfo=PARIS)


def test_render_sms_body_appends_stop_notice_once():
    from app.services.campaign_runner import render_sms_body

    body = render_sms_body(
        "Bonjour pour {title}",
        title="Clio",
        url="https://example.com/listing/1",
    )
    assert "Bonjour pour Clio" in body
    assert "STOP au XXXX pour ne plus recevoir de SMS" in body

    already_present = render_sms_body(
        "Bonjour {title}\nSTOP au XXXX pour ne plus recevoir de SMS",
        title="Clio",
        url="https://example.com/listing/1",
    )
    assert already_present.count("STOP au XXXX pour ne plus recevoir de SMS") == 1


@pytest.mark.asyncio
async def test_select_best_sim_picks_highest_quota():
    from app.services.campaign_runner import _select_best_sim

    sims = [
        {"id": "sim_01", "status": "active"},
        {"id": "sim_02", "status": "active"},
        {"id": "sim_03", "status": "ralenti"},
    ]
    quotas = {"sim_01": 10, "sim_02": 14, "sim_03": 20}

    best = await _select_best_sim(sims, quotas)
    assert best["id"] == "sim_02"


@pytest.mark.asyncio
async def test_select_best_sim_none_when_exhausted():
    from app.services.campaign_runner import _select_best_sim

    sims = [{"id": "sim_01", "status": "active"}]
    quotas = {"sim_01": 0}

    best = await _select_best_sim(sims, quotas)
    assert best is None


@pytest.mark.asyncio
async def test_inter_sms_delay_uses_remaining_gap_only():
    from app.services.campaign_runner import _compute_inter_sms_delay_seconds

    last_sent_at = datetime(2026, 6, 18, 8, 1, tzinfo=UTC)

    class _Ctx:
        def __init__(self, db):
            self.db = db

        async def __aenter__(self):
            return self.db

        async def __aexit__(self, exc_type, exc, tb):
            return False

    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=SimpleNamespace(scalar_one_or_none=lambda: last_sent_at)
    )

    now = datetime(2026, 6, 18, 8, 5, tzinfo=UTC)

    with (
        patch("app.services.campaign_runner.get_db", return_value=_Ctx(db)),
        patch("app.services.campaign_runner.random.randint", return_value=300),
    ):
        delay = await _compute_inter_sms_delay_seconds("sim_01", now=now)

    assert delay == 60


@pytest.mark.asyncio
async def test_run_campaign_pauses_when_no_sim_quota():
    from app.models import CampaignStatus, ListingStatus
    from app.services.campaign_runner import run_campaign

    campaign = SimpleNamespace(
        id="camp-1",
        status=CampaignStatus.PENDING,
        sent=0,
        failed=0,
        message_template="Bonjour {title}",
    )
    listing = SimpleNamespace(
        id="listing-1",
        phone="+33600000000",
        status=ListingStatus.NOUVELLE,
        title="Clio",
        url="https://example.com/listing/1",
    )
    captured_updates: list = []

    class _Ctx:
        def __init__(self, db):
            self.db = db

        async def __aenter__(self):
            return self.db

        async def __aexit__(self, exc_type, exc, tb):
            return False

    initial_db = AsyncMock()
    initial_db.get = AsyncMock(return_value=campaign)
    initial_db.flush = AsyncMock()
    initial_db.execute = AsyncMock(
        side_effect=[
            SimpleNamespace(scalar=lambda: 0),
            SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [listing])),
        ]
    )

    final_db = AsyncMock()

    async def _capture(stmt):
        captured_updates.append(stmt)
        return SimpleNamespace()

    final_db.execute = AsyncMock(side_effect=_capture)

    with (
        patch("app.services.campaign_runner.is_within_sms_window", return_value=True),
        patch(
            "app.services.campaign_runner.get_db",
            side_effect=[_Ctx(initial_db), _Ctx(final_db)],
        ),
        patch(
            "app.services.campaign_runner.boundaries.get_sim_list",
            new_callable=AsyncMock,
            return_value=[{"id": "sim_01", "status": "active", "quota_remaining": 0}],
        ),
        patch(
            "app.services.campaign_runner.is_blacklisted",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        result = await run_campaign("11111111-1111-1111-1111-111111111111")

    assert result["status"] == "paused"
    assert result["sent"] == 0
    assert result["failed"] == 0
    assert captured_updates
    assert any(
        getattr(value, "value", None) == CampaignStatus.PAUSED
        for value in captured_updates[-1]._values.values()
    )


@pytest.mark.asyncio
async def test_run_campaign_fails_on_insufficient_credit():
    from app.boundaries import InsufficientCreditError
    from app.models import CampaignStatus, ListingStatus
    from app.services.campaign_runner import run_campaign

    campaign = SimpleNamespace(
        id="camp-1",
        status=CampaignStatus.PENDING,
        sent=0,
        failed=0,
        message_template="Bonjour {title}",
    )
    listing = SimpleNamespace(
        id="listing-1",
        phone="+33600000000",
        status=ListingStatus.NOUVELLE,
        title="Clio",
        url="https://example.com/listing/1",
    )
    captured_updates: list = []

    class _Ctx:
        def __init__(self, db):
            self.db = db

        async def __aenter__(self):
            return self.db

        async def __aexit__(self, exc_type, exc, tb):
            return False

    initial_db = AsyncMock()
    initial_db.get = AsyncMock(return_value=campaign)
    initial_db.flush = AsyncMock()
    initial_db.execute = AsyncMock(
        side_effect=[
            SimpleNamespace(scalar=lambda: 0),
            SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [listing])),
            SimpleNamespace(scalar_one_or_none=lambda: None),
        ]
    )

    final_db = AsyncMock()

    async def _capture(stmt):
        captured_updates.append(stmt)
        return SimpleNamespace()

    final_db.execute = AsyncMock(side_effect=_capture)

    with (
        patch("app.services.campaign_runner.is_within_sms_window", return_value=True),
        patch(
            "app.services.campaign_runner.get_db",
            side_effect=[_Ctx(initial_db), _Ctx(initial_db), _Ctx(final_db)],
        ),
        patch(
            "app.services.campaign_runner.boundaries.get_sim_list",
            new_callable=AsyncMock,
            return_value=[{"id": "sim_01", "status": "active", "quota_remaining": 1}],
        ),
        patch(
            "app.services.campaign_runner.is_blacklisted",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch("app.services.campaign_runner.random.randint", return_value=120),
        patch("app.services.campaign_runner.asyncio.sleep", new_callable=AsyncMock),
        patch(
            "app.services.campaign_runner.boundaries.send_sms",
            new_callable=AsyncMock,
            side_effect=InsufficientCreditError("credits insuffisants"),
        ),
        patch("app.services.campaign_runner.sentry_sdk.capture_exception"),
    ):
        result = await run_campaign("11111111-1111-1111-1111-111111111111")

    assert result["status"] == "failed"
    assert result["failed"] == 1
    assert any(
        getattr(value, "value", None) == CampaignStatus.FAILED
        for value in captured_updates[-1]._values.values()
    )


@pytest.mark.asyncio
async def test_run_campaign_keeps_running_when_more_listings_remain_in_backlog():
    from app.models import CampaignStatus, ListingStatus, SmsStatus
    from app.services.campaign_runner import run_campaign

    batch_size = 200

    campaign = SimpleNamespace(
        id="camp-1",
        status=CampaignStatus.PENDING,
        sent=3,
        failed=1,
        message_template="Bonjour {title}",
    )
    listings = [
        SimpleNamespace(
            id=f"listing-{idx}",
            phone=f"+3360000{idx:04d}",
            status=ListingStatus.NOUVELLE,
            title=f"Voiture {idx}",
            url=f"https://example.com/listing/{idx}",
        )
        for idx in range(batch_size + 1)
    ]
    captured_updates: list = []

    class _Ctx:
        def __init__(self, db):
            self.db = db

        async def __aenter__(self):
            return self.db

        async def __aexit__(self, exc_type, exc, tb):
            return False

    initial_db = AsyncMock()
    initial_db.get = AsyncMock(return_value=campaign)
    initial_db.flush = AsyncMock()
    initial_db.execute = AsyncMock(
        side_effect=[
            SimpleNamespace(scalar=lambda: 0),
            SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: listings)),
        ]
    )

    write_db = AsyncMock()
    write_db.add = lambda obj: None
    write_db.execute = AsyncMock(return_value=SimpleNamespace())

    final_db = AsyncMock()

    async def _capture(stmt):
        captured_updates.append(stmt)
        return SimpleNamespace()

    final_db.execute = AsyncMock(side_effect=_capture)

    with (
        patch("app.services.campaign_runner.is_within_sms_window", return_value=True),
        patch(
            "app.services.campaign_runner.get_db",
            side_effect=[_Ctx(initial_db)]
            + [_Ctx(write_db) for _ in range(batch_size)]
            + [_Ctx(final_db)],
        ),
        patch(
            "app.services.campaign_runner.boundaries.get_sim_list",
            new_callable=AsyncMock,
            return_value=[
                {"id": "sim_01", "status": "active", "quota_remaining": batch_size}
            ],
        ),
        patch(
            "app.services.campaign_runner.is_blacklisted",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "app.services.campaign_runner._compute_inter_sms_delay_seconds",
            new_callable=AsyncMock,
            return_value=0,
        ),
        patch("app.services.campaign_runner.asyncio.sleep", new_callable=AsyncMock),
        patch(
            "app.services.campaign_runner.boundaries.send_sms",
            new_callable=AsyncMock,
            return_value=SimpleNamespace(status=SmsStatus.SENT, cost=0.04),
        ),
    ):
        result = await run_campaign("11111111-1111-1111-1111-111111111111")

    assert result == {"status": "running", "sent": batch_size, "failed": 0}
    assert any(
        getattr(value, "value", None) == CampaignStatus.RUNNING
        for value in captured_updates[-1]._values.values()
    )
    update_params = captured_updates[-1].compile().params
    assert update_params["sent"] == campaign.sent + batch_size
    assert update_params["failed"] == campaign.failed


def test_run_campaign_task_requeues_next_backlog_batch():
    from app.tasks import run_campaign_task

    result = {"status": "running", "sent": 200, "failed": 0}

    with (
        patch("app.services.campaign_runner.run_campaign", new=Mock(return_value=result)),
        patch("app.tasks._run", return_value=result),
        patch("app.tasks.run_campaign_task.apply_async") as apply_async,
    ):
        returned = run_campaign_task.run("11111111-1111-1111-1111-111111111111")

    assert returned == result
    apply_async.assert_called_once_with(
        args=["11111111-1111-1111-1111-111111111111"]
    )


@pytest.mark.asyncio
async def test_start_campaign_schedules_next_window_when_outside_hours():
    import uuid

    from app.api.campaigns import start_campaign
    from app.models import CampaignStatus

    campaign_id = uuid.uuid4()
    campaign = SimpleNamespace(
        id=campaign_id,
        status=CampaignStatus.PENDING,
        scheduled_at=None,
        last_error="old",
    )
    scheduled_for = datetime(2026, 6, 19, 8, 0, tzinfo=PARIS)

    class _Ctx:
        def __init__(self, db):
            self.db = db

        async def __aenter__(self):
            return self.db

        async def __aexit__(self, exc_type, exc, tb):
            return False

    db = AsyncMock()
    db.get = AsyncMock(return_value=campaign)

    with (
        patch("app.api.campaigns.get_db", return_value=_Ctx(db)),
        patch("app.api.campaigns.is_within_sms_window", return_value=False),
        patch("app.api.campaigns.next_sms_window_start", return_value=scheduled_for),
        patch("app.tasks.run_campaign_task.apply_async") as apply_async,
    ):
        result = await start_campaign(campaign_id)

    apply_async.assert_called_once_with(args=[str(campaign_id)], eta=scheduled_for)
    assert result["queued"] is True
    assert result["scheduled_for"] == scheduled_for.isoformat()
    assert campaign.scheduled_at == scheduled_for
    assert campaign.last_error is None
