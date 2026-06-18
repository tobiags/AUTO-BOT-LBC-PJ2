"""Tests campaign_runner — fenêtre horaire, blacklist, quotas."""
import pytest
from unittest.mock import patch
from datetime import datetime
from zoneinfo import ZoneInfo

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
        {"id": "sim_03", "status": "ralenti"},  # doit être exclu
    ]
    quotas = {"sim_01": 10, "sim_02": 14, "sim_03": 20}

    best = await _select_best_sim(sims, quotas)
    assert best["id"] == "sim_02"  # plus haut quota parmi ACTIVE


@pytest.mark.asyncio
async def test_select_best_sim_none_when_exhausted():
    from app.services.campaign_runner import _select_best_sim

    sims = [{"id": "sim_01", "status": "active"}]
    quotas = {"sim_01": 0}  # quota épuisé

    best = await _select_best_sim(sims, quotas)
    assert best is None
