"""
Module d'analyse véhicule — section dédiée, indépendante des autres routers.

Endpoints :
  POST /analyzer/run/{listing_id}  — analyse directe (réponse immédiate)
  POST /analyzer/run/batch         — lot async via Celery (retourne task_id)
  GET  /analyzer/results           — listings analysés, triés price_score DESC
  GET  /analyzer/stats             — distribution scores + résumé
"""
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from app.db import get_db
from app.models import VehicleAnalysisOut
from app.services.vehicle_analyzer import _CONFIDENCE_HIGH, _CONFIDENCE_MEDIUM
from app.tables import Listing

router = APIRouter(prefix="/analyzer", tags=["analyzer"])


# ── Modèles de réponse locaux ──────────────────────────────────────────────────


class ListingAnalysisResult(BaseModel):
    id: UUID
    url: str
    title: str | None = None
    make: str | None = None
    model: str | None = None
    year: int | None = None
    km: int | None = None
    price: int | None = None
    price_score: float | None = None
    market_avg_price: int | None = None
    market_sample_size: int | None = None
    confidence: str | None = None
    ai_summary: str | None = None

    model_config = {"from_attributes": True}


class AnalyzerStats(BaseModel):
    total_listings: int
    analyzed: int
    pending: int
    high_confidence: int      # sample_size >= 10
    medium_confidence: int    # sample_size >= 5
    underpriced: int          # price_score > 0
    overpriced: int           # price_score < 0
    avg_price_score: float | None = None
    top_opportunities: list[ListingAnalysisResult] = []


class BatchRunResponse(BaseModel):
    task_id: str
    queued: int


def _confidence_from_sample(sample: int | None) -> str:
    if not sample:
        return "insufficient"
    if sample >= _CONFIDENCE_HIGH:
        return "high"
    if sample >= _CONFIDENCE_MEDIUM:
        return "medium"
    return "low"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/run/{listing_id}", response_model=VehicleAnalysisOut)
async def run_single(listing_id: UUID):
    """Analyse une annonce — scoring marché + IA Claude. Réponse immédiate."""
    from app.services.vehicle_analyzer import analyze_listing
    return await analyze_listing(listing_id)


@router.post("/run/batch", response_model=BatchRunResponse)
async def run_batch(
    limit: int = Query(50, ge=1, le=500, description="Nb max d'annonces à analyser"),
    only_with_vehicle_data: bool = Query(
        True, description="Restreindre aux annonces avec make+model renseignés"
    ),
):
    """
    Lance l'analyse d'un lot d'annonces non encore analysées (price_score IS NULL).
    Retourne un task_id Celery — polling via GET /analyzer/results.
    """
    from app.tasks import analyze_batch_task

    async with get_db() as db:
        q = (
            select(Listing.id)
            .where(Listing.price_score.is_(None))
            .order_by(Listing.created_at.desc())
            .limit(limit)
        )
        if only_with_vehicle_data:
            q = q.where(Listing.make.isnot(None), Listing.model.isnot(None))
        result = await db.execute(q)
        ids = [str(row) for row in result.scalars()]

    if not ids:
        return BatchRunResponse(task_id="none", queued=0)

    task = analyze_batch_task.delay(ids)
    return BatchRunResponse(task_id=task.id, queued=len(ids))


@router.get("/results", response_model=list[ListingAnalysisResult])
async def get_results(
    min_score: float | None = Query(None, description="Filtrer price_score >="),
    confidence: str | None = Query(None, description="high | medium | low"),
    limit: int = Query(50, le=200),
):
    """Listings analysés, triés par price_score DESC (= meilleures opportunités en premier)."""
    async with get_db() as db:
        q = (
            select(Listing)
            .where(Listing.price_score.isnot(None))
            .order_by(Listing.price_score.desc())
            .limit(limit)
        )
        if min_score is not None:
            q = q.where(Listing.price_score >= min_score)
        if confidence == "high":
            q = q.where(Listing.market_sample_size >= _CONFIDENCE_HIGH)
        elif confidence == "medium":
            q = q.where(
                Listing.market_sample_size >= _CONFIDENCE_MEDIUM,
                Listing.market_sample_size < _CONFIDENCE_HIGH,
            )
        result = await db.execute(q)
        rows = result.scalars().all()

    return [
        ListingAnalysisResult(
            **{c: getattr(r, c) for c in [
                "id", "url", "title", "make", "model", "year",
                "km", "price", "price_score", "market_avg_price",
                "market_sample_size", "ai_summary",
            ]},
            confidence=_confidence_from_sample(r.market_sample_size),
        )
        for r in rows
    ]


@router.get("/stats", response_model=AnalyzerStats)
async def get_stats():
    """Distribution des scores, nb analysés vs en attente, top 5 opportunités."""
    async with get_db() as db:
        total = (await db.execute(select(func.count(Listing.id)))).scalar() or 0
        analyzed = (
            await db.execute(
                select(func.count(Listing.id)).where(Listing.price_score.isnot(None))
            )
        ).scalar() or 0
        high_conf = (
            await db.execute(
                select(func.count(Listing.id)).where(
                    Listing.market_sample_size >= _CONFIDENCE_HIGH
                )
            )
        ).scalar() or 0
        med_conf = (
            await db.execute(
                select(func.count(Listing.id)).where(
                    Listing.market_sample_size >= _CONFIDENCE_MEDIUM,
                    Listing.market_sample_size < _CONFIDENCE_HIGH,
                )
            )
        ).scalar() or 0
        underpriced = (
            await db.execute(
                select(func.count(Listing.id)).where(Listing.price_score > 0)
            )
        ).scalar() or 0
        overpriced = (
            await db.execute(
                select(func.count(Listing.id)).where(Listing.price_score < 0)
            )
        ).scalar() or 0
        avg_score_row = (
            await db.execute(
                select(func.avg(Listing.price_score)).where(
                    Listing.price_score.isnot(None)
                )
            )
        ).scalar()

        top_rows = (
            await db.execute(
                select(Listing)
                .where(Listing.price_score.isnot(None))
                .order_by(Listing.price_score.desc())
                .limit(5)
            )
        ).scalars().all()

    top = [
        ListingAnalysisResult(
            **{c: getattr(r, c) for c in [
                "id", "url", "title", "make", "model", "year",
                "km", "price", "price_score", "market_avg_price",
                "market_sample_size", "ai_summary",
            ]},
            confidence=_confidence_from_sample(r.market_sample_size),
        )
        for r in top_rows
    ]

    return AnalyzerStats(
        total_listings=total,
        analyzed=analyzed,
        pending=total - analyzed,
        high_confidence=high_conf,
        medium_confidence=med_conf,
        underpriced=underpriced,
        overpriced=overpriced,
        avg_price_score=round(float(avg_score_row), 1) if avg_score_row else None,
        top_opportunities=top,
    )
