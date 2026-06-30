"""
Service d'analyse vehicule - Option B, 100% notre infrastructure.
"""
import asyncio
import json
import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select, update

from app.db import get_db
from app.models import VehicleAnalysisOut
from app.tables import Listing

log = logging.getLogger(__name__)

_CONFIDENCE_HIGH = 10
_CONFIDENCE_MEDIUM = 5
_YEAR_WINDOW = 1
_KM_WINDOW = 25_000

_ANALYSIS_TOOL = {
    "name": "vehicle_analysis_result",
    "description": (
        "Retourne l'analyse complete d'un vehicule d'occasion : "
        "fiabilite, problemes connus, inspection, negociation."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reliability_score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
            },
            "ai_summary": {"type": "string"},
            "known_issues": {
                "type": "array",
                "items": {"type": "string"},
            },
            "inspection_tips": {
                "type": "array",
                "items": {"type": "string"},
            },
            "negotiation_tip": {"type": "string"},
        },
        "required": [
            "reliability_score",
            "ai_summary",
            "known_issues",
            "inspection_tips",
            "negotiation_tip",
        ],
    },
}

_SYSTEM_PROMPT = (
    "Tu es un expert automobile francais specialise dans les vehicules d'occasion. "
    "Tu analyses des annonces pour identifier les opportunites d'achat et les risques. "
    "Tes reponses sont concises, precises et exclusivement en francais."
)


@dataclass
class _MarketStats:
    avg: int | None = None
    min: int | None = None
    max: int | None = None
    count: int = 0
    price_score: float | None = None
    confidence: str = "insufficient"


async def _compute_market_stats(
    db,
    make: str,
    model: str,
    year: int,
    km: int,
    current_price: int,
    exclude_id: UUID,
) -> _MarketStats:
    stmt = (
        select(
            func.avg(Listing.price).label("avg"),
            func.min(Listing.price).label("min"),
            func.max(Listing.price).label("max"),
            func.count(Listing.id).label("count"),
        )
        .where(
            Listing.make == make,
            Listing.model == model,
            Listing.year.between(year - _YEAR_WINDOW, year + _YEAR_WINDOW),
            Listing.km.between(km - _KM_WINDOW, km + _KM_WINDOW),
            Listing.price.isnot(None),
            Listing.id != exclude_id,
        )
    )
    row = (await db.execute(stmt)).one()

    stats = _MarketStats(count=row.count or 0)
    if not stats.count:
        return stats

    stats.avg = int(row.avg)
    stats.min = int(row.min)
    stats.max = int(row.max)

    if stats.avg and current_price:
        stats.price_score = round((stats.avg - current_price) / stats.avg * 100, 1)

    if stats.count >= _CONFIDENCE_HIGH:
        stats.confidence = "high"
    elif stats.count >= _CONFIDENCE_MEDIUM:
        stats.confidence = "medium"
    else:
        stats.confidence = "low"

    return stats


async def _ai_analysis(
    make: str,
    model: str,
    year: int | None,
    km: int | None,
    price: int | None,
    fuel: str | None,
    transmission: str | None,
    description: str | None,
    location: str | None,
    market_stats: _MarketStats,
) -> dict:
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.warning("vehicle_analyzer : ANTHROPIC_API_KEY absent - analyse IA ignoree")
        return {}

    from anthropic import AsyncAnthropic

    prompt_parts = [
        "Analyse ce vehicule d'occasion :",
        f"- Marque / Modele : {make} {model}",
    ]
    if year:
        prompt_parts.append(f"- Annee : {year}")
    if km is not None:
        prompt_parts.append(f"- Kilometrage : {km:,} km")
    if price:
        prompt_parts.append(f"- Prix demande : {price:,} EUR")
    if fuel:
        prompt_parts.append(f"- Carburant : {fuel}")
    if transmission:
        prompt_parts.append(f"- Boite : {transmission}")
    if location:
        prompt_parts.append(f"- Localisation : {location}")
    if description:
        prompt_parts.append(f"- Description vendeur : {description[:500]}")
    if market_stats.count:
        prompt_parts.append(f"\nDonnees marche ({market_stats.count} annonces similaires) :")
        prompt_parts.append(f"- Prix moyen : {market_stats.avg:,} EUR")
        prompt_parts.append(f"- Fourchette : {market_stats.min:,} - {market_stats.max:,} EUR")
        if market_stats.price_score is not None:
            sign = "+" if market_stats.price_score >= 0 else ""
            prompt_parts.append(
                f"- Ecart au marche : {sign}{market_stats.price_score:.1f}% "
                f"({'sous-evalue' if market_stats.price_score > 0 else 'sur-evalue'})"
            )

    client = AsyncAnthropic()
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        tools=[_ANALYSIS_TOOL],
        tool_choice={"type": "tool", "name": "vehicle_analysis_result"},
        messages=[{"role": "user", "content": "\n".join(prompt_parts)}],
    )

    if response.usage:
        from app.services.anthropic_tracker import track_usage

        asyncio.create_task(track_usage(response.usage.input_tokens, response.usage.output_tokens))

    tool_block = next((block for block in response.content if block.type == "tool_use"), None)
    if not tool_block:
        log.error("vehicle_analyzer : Claude n'a pas retourne de tool_use block")
        return {}

    return tool_block.input


def _dump_json_list(values: list[str] | None) -> str | None:
    if not values:
        return None
    return json.dumps(values, ensure_ascii=False)


async def _persist_analysis(db, listing_id: UUID, stats: _MarketStats, ai: dict) -> None:
    await db.execute(
        update(Listing)
        .where(Listing.id == listing_id)
        .values(
            price_score=stats.price_score,
            market_avg_price=stats.avg,
            market_sample_size=stats.count,
            reliability_score=ai.get("reliability_score"),
            ai_summary=ai.get("ai_summary"),
            known_issues_json=_dump_json_list(ai.get("known_issues")),
            inspection_tips_json=_dump_json_list(ai.get("inspection_tips")),
            negotiation_tip=ai.get("negotiation_tip"),
        )
    )


async def analyze_listing(listing_id: UUID) -> VehicleAnalysisOut:
    async with get_db() as db:
        listing = await db.get(Listing, listing_id)
        if not listing:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Annonce introuvable")

        stats = _MarketStats()
        if all([listing.make, listing.model, listing.year, listing.km, listing.price]):
            stats = await _compute_market_stats(
                db,
                make=listing.make,
                model=listing.model,
                year=listing.year,
                km=listing.km,
                current_price=listing.price,
                exclude_id=listing_id,
            )

        ai: dict = {}
        if listing.make and listing.model:
            description = None
            if listing.raw_data:
                try:
                    description = json.loads(listing.raw_data).get("body")
                except Exception:
                    description = None

            ai = await _ai_analysis(
                make=listing.make,
                model=listing.model,
                year=listing.year,
                km=listing.km,
                price=listing.price,
                fuel=listing.fuel,
                transmission=listing.transmission,
                description=description,
                location=listing.location,
                market_stats=stats,
            )
        else:
            log.warning(
                "analyze_listing %s : make/model absents - analyse IA ignoree", listing_id
            )

        await _persist_analysis(db, listing_id, stats, ai)

    return VehicleAnalysisOut(
        listing_id=listing_id,
        listing_url=listing.url,
        price_score=stats.price_score,
        market_avg_price=stats.avg,
        market_min_price=stats.min,
        market_max_price=stats.max,
        market_sample_size=stats.count,
        confidence=stats.confidence,
        reliability_score=ai.get("reliability_score"),
        ai_summary=ai.get("ai_summary"),
        known_issues=ai.get("known_issues", []),
        inspection_tips=ai.get("inspection_tips", []),
        negotiation_tip=ai.get("negotiation_tip"),
    )
