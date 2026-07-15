"""Sector collection orchestration with durable checkpoints."""

from datetime import UTC, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.db import get_db
from app.models import CollectionRunStatus, ListingSource
from app.services.listing_persistence import persist_listings
from app.services.resource_lock import claim_resource, release_resource
from app.tables import CollectionRun, Sector, SectorAccount, SectorProxy, SectorSim

PARIS_TZ = ZoneInfo("Europe/Paris")


def is_within_sector_schedule(
    schedule_start: str, schedule_end: str, now: datetime | None = None
) -> bool:
    current = (now or datetime.now(UTC)).astimezone(PARIS_TZ).time()
    start = time.fromisoformat(schedule_start)
    end = time.fromisoformat(schedule_end)
    return start <= current < end if start <= end else current >= start or current < end


def is_sector_due(
    last_started_at: datetime | None, frequency_minutes: int, now: datetime | None = None
) -> bool:
    if last_started_at is None:
        return True
    current = now or datetime.now(UTC)
    if last_started_at.tzinfo is None:
        last_started_at = last_started_at.replace(tzinfo=UTC)
    return current >= last_started_at + timedelta(minutes=frequency_minutes)


async def get_due_sector_ids(now: datetime | None = None) -> list[str]:
    current = now or datetime.now(UTC)
    async with get_db() as db:
        sectors = (await db.execute(select(Sector).where(Sector.status == "actif"))).scalars().all()
        due: list[str] = []
        for sector in sectors:
            latest = (
                await db.execute(
                    select(CollectionRun.started_at)
                    .where(CollectionRun.sector_id == sector.id)
                    .order_by(CollectionRun.started_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if is_within_sector_schedule(
                sector.schedule_start, sector.schedule_end, current
            ) and is_sector_due(latest, sector.frequency_minutes, current):
                due.append(str(sector.id))
        return due


async def collect_sector(sector_id: UUID) -> dict:
    async with get_db() as db:
        sector = (
            await db.execute(select(Sector).where(Sector.id == sector_id))
        ).scalar_one_or_none()
        if sector is None:
            raise ValueError(f"sector not found: {sector_id}")
        now = datetime.now(UTC)
        if not is_within_sector_schedule(sector.schedule_start, sector.schedule_end, now):
            return {"sector_id": str(sector.id), "status": "skipped", "reason": "outside_schedule"}
        previous = (
            await db.execute(
                select(CollectionRun)
                .where(CollectionRun.sector_id == sector_id)
                .order_by(CollectionRun.started_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if previous and not is_sector_due(previous.started_at, sector.frequency_minutes, now):
            return {"sector_id": str(sector.id), "status": "skipped", "reason": "not_due"}
        today_start = (
            now.astimezone(PARIS_TZ)
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .astimezone(UTC)
        )
        seen_today = (
            await db.execute(
                select(func.coalesce(func.sum(CollectionRun.listings_seen), 0)).where(
                    CollectionRun.sector_id == sector.id,
                    CollectionRun.started_at >= today_start,
                    CollectionRun.status == CollectionRunStatus.COMPLETED.value,
                )
            )
        ).scalar_one()
        remaining_volume = sector.daily_volume - int(seen_today)
        if remaining_volume <= 0:
            return {
                "sector_id": str(sector.id),
                "status": "skipped",
                "reason": "daily_volume_reached",
            }
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
        "max_pages": max(1, min(remaining_volume // 20 + 1, 100)),
        "start_page": int(checkpoint.get("next_page", 1)),
    }
    owner = f"collection:{run.id}"
    leases: list[tuple[str, UUID]] = []
    try:
        async with get_db() as db:
            accounts = (
                (
                    await db.execute(
                        select(SectorAccount).where(SectorAccount.sector_id == sector.id)
                    )
                )
                .scalars()
                .all()
            )
            proxies = (
                (await db.execute(select(SectorProxy).where(SectorProxy.sector_id == sector.id)))
                .scalars()
                .all()
            )
            sims = (
                (await db.execute(select(SectorSim).where(SectorSim.sector_id == sector.id)))
                .scalars()
                .all()
            )
        account_id = None
        if sector.source == ListingSource.LBC.value:
            for resource in accounts:
                if await claim_resource("account", resource.id, owner):
                    leases.append(("account", resource.id))
                    account_id = resource.account_id
                    break
            if account_id is None:
                raise RuntimeError("No available LBC account assigned to sector")
        for kind, resources in (("proxy", proxies), ("sim", sims)):
            if resources:
                for resource in resources:
                    if await claim_resource(kind, resource.id, owner):
                        leases.append((kind, resource.id))
                        break
                else:
                    raise RuntimeError(f"No available {kind} assigned to sector")
        if sector.source == ListingSource.LBC.value:
            from app.services.scraper import scrape_lbc

            listings = await scrape_lbc(params, account_id=account_id)
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
    finally:
        for kind, resource_id in leases:
            await release_resource(kind, resource_id, owner)
