"""
Tests vehicle_analyzer — fonctions pures uniquement (@pytest.mark.unit).

Règle TDD : pas de mock DB, pas de mock Claude.
Les fonctions testées ici ne font aucun I/O.
"""
import pytest

from app.services.vehicle_analyzer import (
    _CONFIDENCE_HIGH,
    _CONFIDENCE_MEDIUM,
    _KM_WINDOW,
    _YEAR_WINDOW,
    _MarketStats,
)
from app.services.scraper import _extract_attr, _parse_year


# ── Constantes de fenêtre ────────────────────────────────────────────────────

@pytest.mark.unit
def test_year_window_is_1():
    assert _YEAR_WINDOW == 1


@pytest.mark.unit
def test_km_window_is_25000():
    assert _KM_WINDOW == 25_000


@pytest.mark.unit
def test_confidence_thresholds():
    assert _CONFIDENCE_HIGH == 10
    assert _CONFIDENCE_MEDIUM == 5


# ── _MarketStats.confidence ───────────────────────────────────────────────────

@pytest.mark.unit
def test_market_stats_default_insufficient():
    s = _MarketStats()
    assert s.confidence == "insufficient"
    assert s.count == 0
    assert s.price_score is None


# ── _extract_attr ─────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_extract_attr_found_by_key():
    attrs = [{"key": "brand", "value": "Peugeot"}]
    assert _extract_attr(attrs, "brand") == "Peugeot"


@pytest.mark.unit
def test_extract_attr_uses_value_label_first():
    attrs = [{"key": "fuel", "value": "diesel", "value_label": "Diesel"}]
    assert _extract_attr(attrs, "fuel") == "Diesel"


@pytest.mark.unit
def test_extract_attr_fallback_second_key():
    attrs = [{"key": "u_car_brand", "value": "Renault"}]
    assert _extract_attr(attrs, "brand", "u_car_brand") == "Renault"


@pytest.mark.unit
def test_extract_attr_missing_returns_empty():
    assert _extract_attr([], "brand") == ""


@pytest.mark.unit
def test_extract_attr_empty_value():
    attrs = [{"key": "model", "value": ""}]
    assert _extract_attr(attrs, "model") == ""


# ── _parse_year ───────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_parse_year_full_date():
    assert _parse_year("2018-01") == 2018


@pytest.mark.unit
def test_parse_year_year_only():
    assert _parse_year("2021") == 2021


@pytest.mark.unit
def test_parse_year_empty():
    assert _parse_year("") is None


@pytest.mark.unit
def test_parse_year_none():
    assert _parse_year(None) is None


@pytest.mark.unit
def test_parse_year_invalid():
    assert _parse_year("abcd") is None


# ── Logique price_score ────────────────────────────────────────────────────────

@pytest.mark.unit
def test_price_score_underpriced():
    """Vendeur demande 8 000 €, marché à 10 000 € → +20 % sous marché."""
    market_avg = 10_000
    listing_price = 8_000
    score = round((market_avg - listing_price) / market_avg * 100, 1)
    assert score == 20.0


@pytest.mark.unit
def test_price_score_overpriced():
    """Vendeur demande 12 000 €, marché à 10 000 € → -20 % (sur-évalué)."""
    market_avg = 10_000
    listing_price = 12_000
    score = round((market_avg - listing_price) / market_avg * 100, 1)
    assert score == -20.0


@pytest.mark.unit
def test_price_score_at_market():
    market_avg = 9_500
    listing_price = 9_500
    score = round((market_avg - listing_price) / market_avg * 100, 1)
    assert score == 0.0


# ── Priorité SMS : score élevé = cibler en premier ───────────────────────────

@pytest.mark.unit
def test_high_price_score_means_motivated_seller():
    """
    Un price_score > 15 % indique un prix bien sous le marché →
    vendeur motivé → priorité SMS élevée.
    """
    score = 18.5
    is_priority = score > 15
    assert is_priority is True


@pytest.mark.unit
def test_negative_price_score_means_low_priority():
    score = -5.0
    is_priority = score > 15
    assert is_priority is False
