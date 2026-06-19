"""
Tests listing_persistence — déduplication et persistance DB.

Marqués @pytest.mark.integration : nécessitent PostgreSQL (port 5433).
"""
import pytest

from app.models import ListingSource
from app.services.listing_persistence import persist_listings
from app.services.scraper import RawListing


def _make_listing(url: str, source: ListingSource = ListingSource.LBC) -> RawListing:
    return RawListing(
        source=source,
        url=url,
        title="Peugeot 308 1.6 HDi 90ch FAP Confort Pack",
        price=8500,
        km=112000,
        location="Paris (75)",
    )


@pytest.mark.integration
async def test_persist_empty_list():
    result = await persist_listings([])
    assert result == {"inserted": 0, "skipped": 0}


@pytest.mark.integration
async def test_persist_single_listing():
    listing = _make_listing("https://www.leboncoin.fr/vo/test_persist_001.htm")
    result = await persist_listings([listing])
    assert result["inserted"] == 1
    assert result["skipped"] == 0


@pytest.mark.integration
async def test_persist_deduplication_by_url():
    """Deux insertions avec la même URL → 1 inserted + 1 skipped."""
    url = "https://www.leboncoin.fr/vo/test_persist_dedup_001.htm"
    listing = _make_listing(url)

    r1 = await persist_listings([listing])
    r2 = await persist_listings([listing])

    assert r1["inserted"] == 1
    assert r2["inserted"] == 0
    assert r2["skipped"] == 1


@pytest.mark.integration
async def test_persist_listing_without_url_is_skipped():
    listing = RawListing(source=ListingSource.LA_CENTRALE, url="", title="Sans URL")
    result = await persist_listings([listing])
    assert result["skipped"] == 1
    assert result["inserted"] == 0


@pytest.mark.integration
async def test_persist_multiple_listings_mixed():
    """3 annonces dont 1 sans URL et 1 déjà présente."""
    url_existing = "https://www.leboncoin.fr/vo/test_persist_mix_001.htm"
    # Insérer d'abord l'annonce existante
    await persist_listings([_make_listing(url_existing)])

    listings = [
        _make_listing(url_existing),                              # déjà présente → skip
        _make_listing("https://www.leboncoin.fr/vo/test_persist_mix_002.htm"),  # nouveau
        RawListing(source=ListingSource.LBC, url="", title="Sans URL"),         # skip
    ]
    result = await persist_listings(listings)
    assert result["inserted"] == 1
    assert result["skipped"] == 2


@pytest.mark.integration
async def test_persist_la_centrale_listing():
    listing = _make_listing(
        "https://www.lacentrale.fr/auto-occasion-annonce-test_persist_001.html",
        source=ListingSource.LA_CENTRALE,
    )
    result = await persist_listings([listing])
    assert result["inserted"] == 1
