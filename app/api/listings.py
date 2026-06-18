from fastapi import APIRouter, Query
from sqlalchemy import select

from app.db import get_db
from app.models import ListingOut, ListingSource, ListingStatus
from app.tables import Listing

router = APIRouter(prefix="/listings", tags=["listings"])


@router.get("", response_model=list[ListingOut])
async def list_listings(
    source: ListingSource | None = None,
    status: ListingStatus | None = None,
    limit: int = Query(50, le=200),
):
    async with get_db() as db:
        q = select(Listing).order_by(Listing.created_at.desc()).limit(limit)
        if source:
            q = q.where(Listing.source == source)
        if status:
            q = q.where(Listing.status == status)
        result = await db.execute(q)
        return [ListingOut.model_validate(r) for r in result.scalars()]


