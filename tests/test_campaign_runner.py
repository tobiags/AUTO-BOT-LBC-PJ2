"""Tests campaign_runner - fenetre horaire, blacklist, quotas."""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
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
        patch("app.services.campaign_runner.get_db", side_effect=[_Ctx(initial_db), _Ctx(final_db)]),
        patch(
            "app.services.campaign_runner.boundaries.get_sim_list",
            new_callable=AsyncMock,
            return_value=[{"id": "sim_01", "status": "active", "quota_remaining": 0}],
        ),
        patch("app.services.campaign_runner.is_blacklisted", new_callable=AsyncMock, return_value=False),
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
