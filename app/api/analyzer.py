"""
Module d'analyse vehicule - section dediee, independante des autres routers.

Endpoints :
  POST /analyzer/run/{listing_id}  - analyse directe
  POST /analyzer/run/batch         - lot async via Celery
  GET  /analyzer/results           - listings analyses, tries price_score DESC
  GET  /analyzer/stats             - distribution scores + resume
"""
import json
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from app.db import get_db
from app.models import VehicleAnalysisOut
from app.services.vehicle_analyzer import _CONFIDENCE_HIGH, _CONFIDENCE_MEDIUM
from app.tables import Listing

router = APIRouter(prefix="/analyzer", tags=["analyzer"])


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
    reliability_score: int | None = None
    ai_summary: str | None = None
    known_issues: list[str] = []
    inspection_tips: list[str] = []
    negotiation_tip: str | None = None

    model_config = {"from_attributes": True}


class AnalyzerStats(BaseModel):
    total_listings: int
    analyzed: int
    pending: int
    high_confidence: int
    medium_confidence: int
    underpriced: int
    overpriced: int
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


def _parse_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _to_result(row: Listing) -> ListingAnalysisResult:
    known_issues_raw = getattr(row, "known_issues_json", None)
    if known_issues_raw is None:
        known_issues = [str(item) for item in getattr(row, "known_issues", [])]
    else:
        known_issues = _parse_json_list(known_issues_raw)

    inspection_tips_raw = getattr(row, "inspection_tips_json", None)
    if inspection_tips_raw is None:
        inspection_tips = [str(item) for item in getattr(row, "inspection_tips", [])]
    else:
        inspection_tips = _parse_json_list(inspection_tips_raw)

    return ListingAnalysisResult(
        id=row.id,
        url=row.url,
        title=row.title,
        make=row.make,
        model=row.model,
        year=row.year,
        km=row.km,
        price=row.price,
        price_score=row.price_score,
        market_avg_price=row.market_avg_price,
        market_sample_size=row.market_sample_size,
        confidence=_confidence_from_sample(row.market_sample_size),
        reliability_score=row.reliability_score,
        ai_summary=row.ai_summary,
        known_issues=known_issues,
        inspection_tips=inspection_tips,
        negotiation_tip=getattr(row, "negotiation_tip", None),
    )


@router.post("/run/{listing_id}", response_model=VehicleAnalysisOut)
async def run_single(listing_id: UUID):
    from app.services.vehicle_analyzer import analyze_listing

    return await analyze_listing(listing_id)


@router.post("/run/batch", response_model=BatchRunResponse)
async def run_batch(
    limit: int = Query(50, ge=1, le=500, description="Nb max d'annonces a analyser"),
    only_with_vehicle_data: bool = Query(
        True, description="Restreindre aux annonces avec make+model renseignes"
    ),
):
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

    return [_to_result(row) for row in rows]


@router.get("/stats", response_model=AnalyzerStats)
async def get_stats():
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

    return AnalyzerStats(
        total_listings=total,
        analyzed=analyzed,
        pending=total - analyzed,
        high_confidence=high_conf,
        medium_confidence=med_conf,
        underpriced=underpriced,
        overpriced=overpriced,
        avg_price_score=round(float(avg_score_row), 1) if avg_score_row else None,
        top_opportunities=[_to_result(row) for row in top_rows],
    )
