"""
Service d'analyse véhicule — Option B, 100% notre infrastructure.

Deux composants :
  1. Scoring marché  : calcul statistique sur notre propre DB listings
                       (pas de dépendance externe, améliore avec le temps)
  2. Analyse IA      : appel Claude via tool_use → JSON structuré garanti
                       (problèmes connus, points d'inspection, argument de négo)

Point d'entrée public : analyze_listing(listing_id)
"""
import logging
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import func, select, update

from app.config import get_settings
from app.db import get_db
from app.models import VehicleAnalysisOut
from app.tables import Listing

log = logging.getLogger(__name__)

# ── Seuils de confiance ───────────────────────────────────────────────────────
_CONFIDENCE_HIGH = 10
_CONFIDENCE_MEDIUM = 5

# ── Fenêtres de comparaison marché ────────────────────────────────────────────
_YEAR_WINDOW = 1       # ± 1 an
_KM_WINDOW = 25_000    # ± 25 000 km

# ── Schéma tool_use Claude ────────────────────────────────────────────────────
_ANALYSIS_TOOL = {
    "name": "vehicle_analysis_result",
    "description": (
        "Retourne l'analyse complète d'un véhicule d'occasion : "
        "fiabilité, problèmes connus, inspection, négociation."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reliability_score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Score de fiabilité globale du modèle (0=très mauvais, 100=excellent)",
            },
            "ai_summary": {
                "type": "string",
                "description": "Résumé de 2-3 phrases sur ce véhicule et son positionnement marché",
            },
            "known_issues": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Liste des problèmes connus et récurrents sur ce modèle/génération",
            },
            "inspection_tips": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Points précis à vérifier lors de l'inspection physique",
            },
            "negotiation_tip": {
                "type": "string",
                "description": "Argument de négociation basé sur le prix marché et les défauts connus",
            },
        },
        "required": [
            "reliability_score", "ai_summary",
            "known_issues", "inspection_tips", "negotiation_tip",
        ],
    },
}

_SYSTEM_PROMPT = (
    "Tu es un expert automobile français spécialisé dans les véhicules d'occasion. "
    "Tu analyses des annonces pour identifier les opportunités d'achat et les risques. "
    "Tes réponses sont concises, précises et exclusivement en français."
)


# ── Calcul scoring marché ─────────────────────────────────────────────────────

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
    """
    Calcule les statistiques de prix marché depuis notre DB.
    Fenêtre : ±1 an, ±25 000 km, même make+model.
    """
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


# ── Analyse IA Claude ─────────────────────────────────────────────────────────

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
    """
    Appel Claude avec tool_use → JSON structuré garanti.
    Retourne les clés : reliability_score, ai_summary, known_issues,
                        inspection_tips, negotiation_tip.
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        log.warning("vehicle_analyzer : ANTHROPIC_API_KEY absent — analyse IA ignorée")
        return {}

    from anthropic import AsyncAnthropic

    prompt_parts = [
        f"Analyse ce véhicule d'occasion :",
        f"- Marque / Modèle : {make} {model}",
    ]
    if year:
        prompt_parts.append(f"- Année : {year}")
    if km is not None:
        prompt_parts.append(f"- Kilométrage : {km:,} km")
    if price:
        prompt_parts.append(f"- Prix demandé : {price:,} €")
    if fuel:
        prompt_parts.append(f"- Carburant : {fuel}")
    if transmission:
        prompt_parts.append(f"- Boîte : {transmission}")
    if location:
        prompt_parts.append(f"- Localisation : {location}")
    if description:
        prompt_parts.append(f"- Description vendeur : {description[:500]}")

    if market_stats.count:
        prompt_parts.append(
            f"\nDonnées marché ({market_stats.count} annonces similaires) :"
        )
        prompt_parts.append(f"- Prix moyen : {market_stats.avg:,} €")
        prompt_parts.append(f"- Fourchette : {market_stats.min:,} – {market_stats.max:,} €")
        if market_stats.price_score is not None:
            sign = "+" if market_stats.price_score >= 0 else ""
            prompt_parts.append(
                f"- Écart au marché : {sign}{market_stats.price_score:.1f}% "
                f"({'sous-évalué' if market_stats.price_score > 0 else 'sur-évalué'})"
            )

    prompt = "\n".join(prompt_parts)

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        tools=[_ANALYSIS_TOOL],
        tool_choice={"type": "tool", "name": "vehicle_analysis_result"},
        messages=[{"role": "user", "content": prompt}],
    )

    tool_block = next(
        (b for b in response.content if b.type == "tool_use"), None
    )
    if not tool_block:
        log.error("vehicle_analyzer : Claude n'a pas retourné de tool_use block")
        return {}

    return tool_block.input  # dict validé par le schema


# ── Persistance du résultat ───────────────────────────────────────────────────

async def _persist_analysis(db, listing_id: UUID, stats: _MarketStats, ai: dict) -> None:
    await db.execute(
        update(Listing)
        .where(Listing.id == listing_id)
        .values(
            price_score=stats.price_score,
            market_avg_price=stats.avg,
            market_sample_size=stats.count,
            ai_summary=ai.get("ai_summary"),
        )
    )


# ── Point d'entrée public ─────────────────────────────────────────────────────

async def analyze_listing(listing_id: UUID) -> VehicleAnalysisOut:
    """
    Analyse complète d'une annonce :
      1. Charge le listing depuis la DB
      2. Calcule le scoring marché (nos données)
      3. Appelle Claude pour l'analyse textuelle
      4. Persiste le résultat et retourne VehicleAnalysisOut
    """
    async with get_db() as db:
        listing = await db.get(Listing, listing_id)
        if not listing:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Annonce introuvable")

        # Scoring marché — possible seulement si on a make+model+year+km
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

        # Analyse IA — nécessite au minimum make + model
        ai: dict = {}
        if listing.make and listing.model:
            description = None
            if listing.raw_data:
                import json
                try:
                    description = json.loads(listing.raw_data).get("body")
                except Exception:
                    pass

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
                "analyze_listing %s : make/model absents — analyse IA ignorée", listing_id
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
