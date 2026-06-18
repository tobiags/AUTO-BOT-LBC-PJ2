"""
Persistance des annonces scrapées → table listings.

Déduplication par URL via ON CONFLICT DO NOTHING (contrainte UNIQUE).
Utilisé par scrape_listings_task après chaque collecte LBC / La Centrale.
"""
import logging

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import get_db
from app.models import ListingStatus
from app.services.scraper import RawListing
from app.tables import Listing

log = logging.getLogger(__name__)


async def persist_listings(listings: list[RawListing]) -> dict:
    """
    Insère les annonces en base avec déduplication par URL.

    Utilise pg_insert.on_conflict_do_nothing(index_elements=["url"]).
    Retourne {"inserted": N, "skipped": N}.
    """
    if not listings:
        return {"inserted": 0, "skipped": 0}

    inserted = skipped = 0

    async with get_db() as db:
        for listing in listings:
            if not listing.url:
                skipped += 1
                continue

            stmt = (
                pg_insert(Listing)
                .values(
                    source=listing.source,
                    url=listing.url,
                    title=listing.title,
                    price=listing.price,
                    km=listing.km,
                    location=listing.location,
                    phone=listing.phone,
                    raw_data=listing.raw_data,
                    make=listing.make,
                    model=listing.model,
                    year=listing.year,
                    fuel=listing.fuel,
                    transmission=listing.transmission,
                    status=ListingStatus.NOUVELLE,
                )
                .on_conflict_do_nothing(index_elements=["url"])
                .returning(Listing.id)
            )
            result = await db.execute(stmt)
            if result.scalar():
                inserted += 1
            else:
                skipped += 1

    log.info("persist_listings : inserted=%d skipped=%d", inserted, skipped)
    return {"inserted": inserted, "skipped": skipped}
