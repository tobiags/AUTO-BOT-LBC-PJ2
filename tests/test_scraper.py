"""
Tests unitaires scraper — fonctions pures (pas de I/O réelle).

Règle TDD : seul boundaries.py est mocké.
Les fonctions de parsing et d'enrichissement sont testées directement.
"""
import pytest

from app.models import ListingSource
from app.services.scraper import RawListing, _parse_km, _parse_price, enrich_with_phone


# ── _parse_price ──────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_parse_price_fr_spacing():
    assert _parse_price("15 900 €") == 15900


@pytest.mark.unit
def test_parse_price_compact():
    assert _parse_price("8500€") == 8500


@pytest.mark.unit
def test_parse_price_empty():
    assert _parse_price("") is None


@pytest.mark.unit
def test_parse_price_none():
    assert _parse_price(None) is None


@pytest.mark.unit
def test_parse_price_text_only():
    assert _parse_price("Prix non communiqué") is None


# ── _parse_km ────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_parse_km_with_unit():
    assert _parse_km("35 000 km") == 35000


@pytest.mark.unit
def test_parse_km_compact():
    assert _parse_km("150000km") == 150000


@pytest.mark.unit
def test_parse_km_empty():
    assert _parse_km("") is None


@pytest.mark.unit
def test_parse_km_none():
    assert _parse_km(None) is None


# ── enrich_with_phone ─────────────────────────────────────────────────────────

@pytest.mark.unit
def test_enrich_adds_phone_from_title():
    listing = RawListing(
        source=ListingSource.LBC,
        url="https://www.leboncoin.fr/vo/1234.htm",
        title="Peugeot 308 - Appelez le 06 12 34 56 78",
    )
    result = enrich_with_phone(listing)
    assert result.phone == "+33612345678"


@pytest.mark.unit
def test_enrich_does_not_overwrite_existing_phone():
    listing = RawListing(
        source=ListingSource.LBC,
        url="https://www.leboncoin.fr/vo/5678.htm",
        title="Tel 06 12 34 56 78",
        phone="+33699887766",
    )
    result = enrich_with_phone(listing)
    assert result.phone == "+33699887766"


@pytest.mark.unit
def test_enrich_returns_none_when_no_phone():
    listing = RawListing(
        source=ListingSource.LA_CENTRALE,
        url="https://www.lacentrale.fr/auto-occasion-annonce-1.html",
        title="Renault Clio sans numéro",
    )
    result = enrich_with_phone(listing)
    assert result.phone is None


@pytest.mark.unit
def test_enrich_preserves_all_fields():
    listing = RawListing(
        source=ListingSource.LA_CENTRALE,
        url="https://www.lacentrale.fr/auto-occasion-annonce-2.html",
        title="BMW 320d",
        price=18500,
        km=87000,
        location="Lyon (69)",
    )
    result = enrich_with_phone(listing)
    assert result.source == ListingSource.LA_CENTRALE
    assert result.price == 18500
    assert result.km == 87000
    assert result.location == "Lyon (69)"


@pytest.mark.unit
def test_enrich_no_title_returns_unchanged():
    listing = RawListing(
        source=ListingSource.LBC,
        url="https://www.leboncoin.fr/vo/9999.htm",
    )
    result = enrich_with_phone(listing)
    assert result.phone is None
    assert result.title is None
