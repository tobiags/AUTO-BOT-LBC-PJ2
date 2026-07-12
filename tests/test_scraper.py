"""
Tests unitaires scraper - fonctions pures (pas de I/O reelle).
"""
import pytest

from app.models import ListingSource
from app.services.scraper import (
    RawListing,
    _page_url,
    _parse_km,
    _parse_lbc_search_items,
    _parse_price,
    _pick_lbc_title,
    enrich_with_phone,
)


@pytest.mark.unit
def test_page_url_preserves_filters_and_replaces_page():
    url = _page_url("https://example.test/search?q=citroen&page=2", 7)
    assert "q=citroen" in url
    assert "page=7" in url


@pytest.mark.unit
def test_parse_price_fr_spacing():
    assert _parse_price("15 900 EUR") == 15900


@pytest.mark.unit
def test_parse_price_compact():
    assert _parse_price("8500EUR") == 8500


@pytest.mark.unit
def test_parse_price_empty():
    assert _parse_price("") is None


@pytest.mark.unit
def test_parse_price_none():
    assert _parse_price(None) is None


@pytest.mark.unit
def test_parse_price_text_only():
    assert _parse_price("Prix non communique") is None


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


@pytest.mark.unit
def test_pick_lbc_title_prefers_semantic_title():
    assert _pick_lbc_title(
        "Peugeot 308 HDi",
        "Peugeot 308 HDi\n9 500 EUR\nBordeaux 33000",
        "Bordeaux 33000",
    ) == "Peugeot 308 HDi"


@pytest.mark.unit
def test_pick_lbc_title_falls_back_to_text_lines():
    assert _pick_lbc_title(
        "9 500 EUR",
        "Renault Clio 4\n9 500 EUR\nParis 75001",
        "Paris 75001",
    ) == "Renault Clio 4"


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
        title="Renault Clio sans numero",
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
def test_enrich_preserves_vehicle_metadata():
    listing = RawListing(
        source=ListingSource.LBC,
        url="https://www.leboncoin.fr/vo/metadata.htm",
        title="BMW 320d contactez le 06 12 34 56 78",
        make="BMW",
        model="320d",
        year=2021,
        fuel="diesel",
        transmission="auto",
    )
    result = enrich_with_phone(listing)
    assert result.phone == "+33612345678"
    assert result.make == "BMW"
    assert result.model == "320d"
    assert result.year == 2021
    assert result.fuel == "diesel"
    assert result.transmission == "auto"


@pytest.mark.unit
def test_enrich_no_title_returns_unchanged():
    listing = RawListing(
        source=ListingSource.LBC,
        url="https://www.leboncoin.fr/vo/9999.htm",
    )
    result = enrich_with_phone(listing)
    assert result.phone is None
    assert result.title is None


@pytest.mark.unit
def test_parse_lbc_search_items_basic():
    items = _parse_lbc_search_items([{
        "url": "https://www.leboncoin.fr/voitures/123456789.htm",
        "title": "Peugeot 308 HDi 90",
        "price": "9 500 EUR",
        "location": "Bordeaux 33000",
        "text": "Peugeot 308 HDi 90\n9 500 EUR\nBordeaux 33000",
    }])
    assert len(items) == 1
    item = items[0]
    assert item.source == ListingSource.LBC
    assert item.title == "Peugeot 308 HDi 90"
    assert item.price == 9500
    assert item.location == "Bordeaux 33000"


@pytest.mark.unit
def test_parse_lbc_search_items_ignores_empty_urls():
    items = _parse_lbc_search_items([{"url": "", "text": "Annonce vide"}])
    assert items == []


@pytest.mark.unit
def test_parse_lbc_search_items_can_extract_phone_from_text_fallback():
    items = _parse_lbc_search_items([{
        "url": "https://www.leboncoin.fr/voitures/987654321.htm",
        "title": "12 000 EUR",
        "price": "12 000 EUR",
        "location": "Lille 59000",
        "text": "Citroen C3 appelez le 06 12 34 56 78\n12 000 EUR\nLille 59000",
    }])
    assert items[0].title == "Citroen C3 appelez le 06 12 34 56 78"
    assert items[0].phone == "+33612345678"
