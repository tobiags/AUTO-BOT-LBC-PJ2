"""Sector collection orchestration with durable checkpoints."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.db import get_db
from app.models import CollectionRunStatus, ListingSource
from app.services.listing_persistence import persist_listings
from app.tables import CollectionRun, Sector


async def collect_sector(sector_id: UUID) -> dict:
    async with get_db() as db:
        sector = (
            await db.execute(select(Sector).where(Sector.id == sector_id))
        ).scalar_one_or_none()
        if sector is None:
            raise ValueError(f"sector not found: {sector_id}")
        previous = (
            await db.execute(
                select(CollectionRun)
                .where(CollectionRun.sector_id == sector_id)
                .order_by(CollectionRun.started_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        checkpoint = (previous.checkpoint if previous else {}) or {}
        run = CollectionRun(sector_id=sector.id, source=sector.source, checkpoint=checkpoint)
        db.add(run)
        await db.flush()

    params = {
        "marque": sector.brand_model or "",
        "modele": "",
        "km_max": sector.mileage_max or 2_000_000,
        "prix_min": sector.price_min,
        "prix_max": sector.price_max or 2_000_000,
        "region": sector.region,
        "department": sector.department,
        "max_pages": max(1, min(sector.daily_volume // 20 + 1, 100)),
        "start_page": int(checkpoint.get("next_page", 1)),
    }
    try:
        if sector.source == ListingSource.LBC.value:
            from app.services.scraper import scrape_lbc

            listings = await scrape_lbc(params)
        elif sector.source == ListingSource.LA_CENTRALE.value:
            from app.services.scraper import scrape_la_centrale

            listings = await scrape_la_centrale(params)
        else:
            raise ValueError(f"unsupported source: {sector.source}")
        persisted = await persist_listings(listings, sector_id=sector.id)
        now = datetime.now(UTC)
        async with get_db() as db:
            current = await db.get(CollectionRun, run.id)
            current.status = CollectionRunStatus.COMPLETED.value
            current.listings_seen = len(listings)
            current.checkpoint = {
                "next_page": params["start_page"] + params["max_pages"],
                "last_run_at": now.isoformat(),
            }
            current.finished_at = now
        return {
            "sector_id": str(sector.id),
            "source": sector.source,
            **persisted,
            "seen": len(listings),
        }
    except Exception as exc:
        async with get_db() as db:
            current = await db.get(CollectionRun, run.id)
            current.status = CollectionRunStatus.FAILED.value
            current.last_error = str(exc)[:1000]
            current.finished_at = datetime.now(UTC)
        raise
