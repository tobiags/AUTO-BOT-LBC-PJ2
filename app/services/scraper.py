"""
Collecte d'annonces — LeBonCoin + La Centrale (Workflow WF-04).

LBC         : session Patchright avec profil persistant (compte ACTIF).
La Centrale : crawl4ai AsyncWebCrawler + JsonCssExtractionStrategy (pas de DataDome).

Format unifié de sortie : RawListing
"""
import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from app.models import ListingSource
from app.services.phone_extractor import extract_phone

log = logging.getLogger(__name__)

# ── Schéma CSS La Centrale ────────────────────────────────────────────────────
# Sélecteurs basés sur l'inspection du site (à réviser si La Centrale refactorise).
# baseSelector cible les cartes d'annonces dans la liste de résultats.
_LC_SCHEMA = {
    "name": "Annonces La Centrale",
    "baseSelector": "article.listing-item, div[class*='AdCard'], div[class*='listing-card']",
    "fields": [
        {"name": "title",    "selector": "h2, h3, [class*='title']",             "type": "text"},
        {"name": "price",    "selector": "[class*='price'], [class*='Price']",    "type": "text"},
        {"name": "km",       "selector": "[class*='mileage'], [class*='km']",     "type": "text"},
        {"name": "location", "selector": "[class*='location']",                  "type": "text"},
        {"name": "url",      "selector": "a[href]", "type": "attribute", "attribute": "href"},
    ],
}

# Attribut stable LBC (test-id exposé dans leur React) — moins fragile que les classes CSS.
_LBC_JS_EXTRACT = """
() => Array.from(
    document.querySelectorAll('[data-qa-id="aditem_container"]')
).map(el => ({
    title:    el.querySelector('[data-qa-id="aditem_title"]')?.innerText   ?? '',
    price:    el.querySelector('[data-qa-id="aditem_price"]')?.innerText   ?? '',
    location: el.querySelector('[data-qa-id="aditem_location"]')?.innerText ?? '',
    url:      el.querySelector('a[href]')?.href ?? '',
}))
"""


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


def _parse_price(text: str) -> int | None:
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def _parse_km(text: str) -> int | None:
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


async def scrape_lbc(search_params: dict[str, Any]) -> list[RawListing]:
    """
    Scrape LeBonCoin via Patchright avec un compte ACTIF (session persistante).

    Le compte ACTIF fournit les cookies DataDome nécessaires pour contourner
    la protection anti-bot. La session est chargée depuis PlatformAccount.session_path.

    search_params : {"marque": str, "modele": str, "km_max": int, "prix_max": int}
    """
    from patchright.async_api import async_playwright
    from sqlalchemy import select

    from app.db import get_db
    from app.tables import PlatformAccount

    # ── Récupérer un compte ACTIF avec session Patchright ──────────────────────
    async with get_db() as db:
        result = await db.execute(
            select(PlatformAccount)
            .where(
                PlatformAccount.status == "ACTIF",
                PlatformAccount.session_path.isnot(None),
            )
            .order_by(PlatformAccount.derniere_action.asc().nullslast())
            .limit(1)
        )
        account = result.scalar_one_or_none()

    if not account:
        log.warning("scrape_lbc : aucun compte ACTIF avec session_path disponible")
        return []

    marque = search_params.get("marque", "")
    modele = search_params.get("modele", "")
    km_max = search_params.get("km_max", 150000)
    prix_max = search_params.get("prix_max", 50000)

    search_url = (
        f"https://www.leboncoin.fr/voitures/offres/?q={marque}+{modele}"
        f"&mileage_max={km_max}&price_max={prix_max}&sort=time&order=desc"
    )

    listings: list[RawListing] = []

    async with async_playwright() as p:
        # Charger le profil persistant — cookies DataDome inclus
        ctx = await p.chromium.launch_persistent_context(
            account.session_path,
            headless=True,
            focus_control=False,
            # Pas de proxy pour le scraping : le compte est déjà authentifié côté LBC
        )
        try:
            page = await ctx.new_page()
            await page.goto(search_url, wait_until="networkidle", timeout=30_000)

            # Attendre les annonces ou timeout gracieux
            try:
                await page.wait_for_selector(
                    '[data-qa-id="aditem_container"]', timeout=15_000
                )
            except Exception:
                log.warning(
                    "scrape_lbc : sélecteur annonces absent — titre page: %s",
                    await page.title(),
                )
                return []

            # Extraction JS en contexte isolé (stealth Patchright)
            raw_items: list[dict] = await page.evaluate(
                _LBC_JS_EXTRACT, isolated_context=True
            )

            for item in raw_items:
                listing = RawListing(
                    source=ListingSource.LBC,
                    url=item.get("url", ""),
                    title=item.get("title", "").strip() or None,
                    price=_parse_price(item.get("price", "")),
                    location=item.get("location", "").strip() or None,
                    raw_data=json.dumps(item, ensure_ascii=False),
                )
                listing = enrich_with_phone(listing)
                listings.append(listing)

        finally:
            await ctx.close()

    log.info("scrape_lbc : %d annonces collectées (compte=%s)", len(listings), account.id)
    return listings


async def scrape_la_centrale(search_params: dict[str, Any]) -> list[RawListing]:
    """
    Scrape La Centrale via crawl4ai + JsonCssExtractionStrategy.

    La Centrale n'utilise pas DataDome → accès direct possible.
    simulate_user=True + magic=True pour contourner les protections basiques.

    search_params : {"marque": str, "modele": str, "km_max": int, "prix_max": int}
    """
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
    from crawl4ai import JsonCssExtractionStrategy

    marque = search_params.get("marque", "")
    modele = search_params.get("modele", "")
    km_max = search_params.get("km_max", 150000)
    prix_max = search_params.get("prix_max", 50000)

    # Encodage minimal pour les paramètres URL
    makes_models = f"{marque.lower()}%3A{modele.lower()}"
    search_url = (
        f"https://www.lacentrale.fr/listing"
        f"?makesModelsCommercialNames={makes_models}"
        f"&mileageMax={km_max}&priceMax={prix_max}"
        f"&sortBy=NEW&sortOrder=1"
    )

    browser_config = BrowserConfig(headless=True, java_script_enabled=True)
    crawler_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        extraction_strategy=JsonCssExtractionStrategy(_LC_SCHEMA),
        simulate_user=True,
        magic=True,
        wait_for="css:article, css:div[class*='AdCard'], css:div[class*='listing']",
        wait_for_timeout=15_000,
        page_timeout=30_000,
    )

    listings: list[RawListing] = []
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=search_url, config=crawler_config)

    if not result.success:
        log.warning("crawl4ai La Centrale échoué : %s", result.error_message)
        return []

    if not result.extracted_content:
        log.warning("crawl4ai La Centrale : extracted_content vide")
        return []

    raw_items: list[dict] = json.loads(result.extracted_content)
    for item in raw_items:
        raw_url = item.get("url", "")
        # La Centrale peut retourner des URLs relatives
        if raw_url and not raw_url.startswith("http"):
            raw_url = f"https://www.lacentrale.fr{raw_url}"

        listing = RawListing(
            source=ListingSource.LA_CENTRALE,
            url=raw_url,
            title=item.get("title", "").strip() or None,
            price=_parse_price(item.get("price", "")),
            km=_parse_km(item.get("km", "")),
            location=item.get("location", "").strip() or None,
            raw_data=json.dumps(item, ensure_ascii=False),
        )
        listing = enrich_with_phone(listing)
        listings.append(listing)

    log.info("scrape_la_centrale : %d annonces collectées", len(listings))
    return listings


def enrich_with_phone(listing: RawListing) -> RawListing:
    """Extrait le numéro de téléphone depuis le titre si absent (regex)."""
    if listing.phone or not listing.title:
        return listing

    phone = extract_phone(listing.title)
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
