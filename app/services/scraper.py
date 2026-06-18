"""
Collecte d'annonces — LeBonCoin + La Centrale (Workflow WF-04).

LBC         : session Patchright avec profil persistant (compte ACTIF).
               Approche 1 (primaire)  : extraction DOM via data-qa-id (stable).
               Approche 2 (fallback)  : POST /finder/search depuis page.evaluate()
                                        — même tab LBC, DataDome transparent.
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

# ── LBC approche 1 : DOM via data-qa-id ──────────────────────────────────────
# Attributs test-id exposés dans leur React — moins fragiles que les classes CSS (R08).
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

# ── LBC approche 2 : API /finder/search depuis le tab ────────────────────────
# api_key publique dans le JS bundle LBC (visible dans les DevTools réseau).
# L'appel fetch est exécuté depuis une vraie tab leboncoin.fr → DataDome le laisse passer.
_LBC_API_KEY = "ba0c2dad52b3ec"
_LBC_API_URL = "https://api.leboncoin.fr/finder/search"

_LBC_API_JS_FETCH = f"""
async (payload) => {{
    try {{
        const resp = await fetch('{_LBC_API_URL}', {{
            method: 'POST',
            credentials: 'include',
            headers: {{
                'content-type': 'application/json',
                'api_key': '{_LBC_API_KEY}',
            }},
            body: JSON.stringify(payload),
        }});
        if (!resp.ok) return null;
        return await resp.json();
    }} catch (e) {{
        return null;
    }}
}}
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


def _build_lbc_api_payload(search_params: dict[str, Any], offset: int = 0, limit: int = 100) -> dict:
    """Construit le body JSON pour POST /finder/search."""
    keywords = " ".join(filter(None, [
        search_params.get("marque", ""),
        search_params.get("modele", ""),
    ])).strip()

    ranges: dict = {}
    if search_params.get("prix_max"):
        ranges["price"] = {"max": int(search_params["prix_max"])}
    if search_params.get("km_max"):
        ranges["mileage"] = {"max": int(search_params["km_max"])}

    return {
        "sort_by": "time",
        "sort_order": "desc",
        "limit": limit,
        "limit_alu": 3,
        "offset": offset,
        "disable_total": False,
        "extend": True,
        "listing_source": "direct-search" if offset == 0 else "pagination",
        "filters": {
            "category": {"id": "2"},          # Voitures
            "enums": {"ad_type": ["offer"]},
            "keywords": {"text": keywords},
            "ranges": ranges,
        },
    }


def _parse_api_items(ads: list[dict]) -> list[RawListing]:
    """Convertit les annonces JSON de /finder/search en RawListing."""
    results: list[RawListing] = []
    for ad in ads:
        subject = ad.get("subject", "")
        price_raw = ad.get("price", [])
        price = int(price_raw[0]) if price_raw else None

        # Kilométrage dans attributes [{key, value}]
        km: int | None = None
        for attr in ad.get("attributes", []):
            if attr.get("key") == "mileage":
                km = _parse_km(str(attr.get("value", "")))
                break

        location_data = ad.get("location", {})
        location = ", ".join(filter(None, [
            location_data.get("city", ""),
            location_data.get("zipcode", ""),
        ])) or None

        listing = RawListing(
            source=ListingSource.LBC,
            url=ad.get("url", ""),
            title=subject.strip() or None,
            price=price,
            km=km,
            location=location,
            raw_data=json.dumps(ad, ensure_ascii=False),
        )
        results.append(enrich_with_phone(listing))
    return results


async def scrape_lbc(search_params: dict[str, Any]) -> list[RawListing]:
    """
    Scrape LeBonCoin via Patchright avec un compte ACTIF (session persistante).

    Stratégie duale (robustesse) :
      1. DOM primaire  : data-qa-id stables (rapide, pas de réseau supplémentaire)
      2. API fallback  : POST /finder/search depuis page.evaluate() dans le même tab
                         → DataDome transparent car requête issue d'un vrai contexte LBC

    search_params : {"marque": str, "modele": str, "km_max": int, "prix_max": int}
    """
    from patchright.async_api import async_playwright
    from sqlalchemy import select

    from app.db import get_db
    from app.tables import PlatformAccount

    # ── Récupérer un compte ACTIF avec session Patchright ─────────────────────
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
        )
        try:
            page = await ctx.new_page()
            await page.goto(search_url, wait_until="networkidle", timeout=30_000)

            # ── Approche 1 : DOM extraction ────────────────────────────────────
            dom_ok = False
            try:
                await page.wait_for_selector(
                    '[data-qa-id="aditem_container"]', timeout=15_000
                )
                raw_items: list[dict] = await page.evaluate(
                    _LBC_JS_EXTRACT, isolated_context=True
                )
                if raw_items:
                    dom_ok = True
                    for item in raw_items:
                        listing = RawListing(
                            source=ListingSource.LBC,
                            url=item.get("url", ""),
                            title=item.get("title", "").strip() or None,
                            price=_parse_price(item.get("price", "")),
                            location=item.get("location", "").strip() or None,
                            raw_data=json.dumps(item, ensure_ascii=False),
                        )
                        listings.append(enrich_with_phone(listing))
                    log.info(
                        "scrape_lbc DOM : %d annonces (compte=%s)",
                        len(listings), account.id,
                    )
            except Exception as exc:
                log.warning("scrape_lbc DOM échoué : %s — bascule API", exc)

            # ── Approche 2 : API /finder/search (fallback si DOM vide/bloqué) ──
            if not dom_ok:
                log.info("scrape_lbc : DOM vide, tentative API /finder/search")
                payload = _build_lbc_api_payload(search_params)
                try:
                    api_resp = await page.evaluate(
                        _LBC_API_JS_FETCH, payload, isolated_context=True
                    )
                    ads: list[dict] = (api_resp or {}).get("ads", [])
                    if ads:
                        listings = _parse_api_items(ads)
                        log.info(
                            "scrape_lbc API : %d annonces (compte=%s)",
                            len(listings), account.id,
                        )
                    else:
                        log.warning(
                            "scrape_lbc API : réponse vide (resp=%s)", api_resp
                        )
                except Exception as exc:
                    log.error("scrape_lbc API échoué : %s", exc)

        finally:
            await ctx.close()

    log.info("scrape_lbc : total %d annonces collectées", len(listings))
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
