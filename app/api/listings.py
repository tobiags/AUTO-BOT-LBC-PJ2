from uuid import UUID

from fastapi import APIRouter, Query

from app.db import get_db
from app.models import ListingOut, ListingSource, ListingStatus, VehicleAnalysisOut
from app.tables import Listing
from sqlalchemy import select

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


@router.post("/{listing_id}/analyze", response_model=VehicleAnalysisOut, tags=["listings"])
async def analyze_listing_endpoint(listing_id: UUID):
    """
    Lance l'analyse complète d'une annonce :
    - Score de prix vs marché (nos données DB)
    - Analyse IA Claude : fiabilité, problèmes connus, inspection, négociation
    Persiste le résultat dans la table listings (price_score, market_avg_price, ai_summary).
    """
    from app.services.vehicle_analyzer import analyze_listing
    return await analyze_listing(listing_id)
