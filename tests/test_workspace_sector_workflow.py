from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.models import ListingSource, SectorCreate, UserCreate, UserRole
from app.services.listing_persistence import listing_content_hash
from app.services.scraper import RawListing
from app.services.sector_collection import is_sector_due, is_within_sector_schedule


def test_sector_requires_region_and_department_and_validates_price_range():
    sector = SectorCreate(
        name="Bretagne 35",
        source=ListingSource.LBC,
        region="Bretagne",
        department="35",
        price_min=5000,
        price_max=15000,
    )
    assert sector.department == "35"
    with pytest.raises(ValidationError):
        SectorCreate(
            name="invalid",
            source=ListingSource.LBC,
            region="Bretagne",
            department="35",
            price_min=20_000,
            price_max=10_000,
        )


def test_user_roles_are_limited_to_dashboard_roles():
    assert (
        UserCreate(email="a@example.test", display_name="A", role=UserRole.MANAGER).role
        == UserRole.MANAGER
    )
    with pytest.raises(ValidationError):
        UserCreate(email="a@example.test", display_name="A", role="viewer")


def test_listing_hash_changes_when_listing_content_changes():
    base = RawListing(
        source=ListingSource.LBC,
        url="https://example.test/1",
        title="Clio",
        price=10000,
        location="35",
    )
    changed = RawListing(
        source=ListingSource.LBC,
        url="https://example.test/2",
        title="Clio",
        price=11000,
        location="35",
    )
    assert listing_content_hash(base) != listing_content_hash(changed)
    assert listing_content_hash(base) == listing_content_hash(base)


def test_sector_is_due_only_after_its_frequency_and_inside_its_schedule():
    now = datetime(2026, 7, 15, 10, 0, tzinfo=UTC)
    assert is_within_sector_schedule("08:00", "20:00", now)
    assert not is_within_sector_schedule("08:00", "09:00", now)
    assert not is_sector_due(now - timedelta(minutes=30), 60, now)
    assert is_sector_due(now - timedelta(minutes=60), 60, now)
