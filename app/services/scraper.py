"""
Collecte d'annonces — LeBonCoin + La Centrale (Workflow WF-04).

LBC : session Patchright avec cookies DataDome depuis DB (compte ACTIF).
La Centrale : crawl4ai direct (pas de DataDome).

Format unifié de sortie : { titre, prix, km, lieu, url, téléphone, source }
"""
import logging
from dataclasses import dataclass
from typing import Any

from app.models import ListingSource
from app.services.phone_extractor import extract_phone_with_fallback

log = logging.getLogger(__name__)


@dataclass
class RawListing:
    source: ListingSource
    url: str
    title: str | None = None
    price: int | None = None
    km: int | None = None
    location: str | None = None
    phone: str | None = None
    raw_data: str | None = None


async def scrape_lbc(search_params: dict[str, Any]) -> list[RawListing]:
    """
    Scrape LeBonCoin avec Patchright + compte ACTIF.
    TODO (Sprint 3) : implémenter navigation Patchright.

    search_params : {
        "marque": "Peugeot", "modele": "308",
        "km_max": 150000, "prix_max": 15000,
        "zone": "Île-de-France"
    }
    """
    log.info("Scraping LBC — stub actif (Sprint 3 implantera Patchright). params=%s", search_params)
    return []


async def scrape_la_centrale(search_params: dict[str, Any]) -> list[RawListing]:
    """
    Scrape La Centrale avec crawl4ai (accès direct, pas de DataDome).
    TODO (Sprint 3) : implémenter.
    """
    log.info("Scraping La Centrale — stub actif (Sprint 3). params=%s", search_params)
    return []


async def enrich_with_phone(listing: RawListing) -> RawListing:
    """
    Extrait le numéro depuis le titre/description si absent.
    Utilise extract_phone_with_fallback (regex → Claude Haiku).
    """
    if listing.phone or not listing.title:
        return listing

    phone = await extract_phone_with_fallback(listing.title)
    return RawListing(
        source=listing.source,
        url=listing.url,
        title=listing.title,
        price=listing.price,
        km=listing.km,
        location=listing.location,
        phone=phone,
        raw_data=listing.raw_data,
    )
