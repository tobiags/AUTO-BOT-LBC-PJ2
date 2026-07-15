"""
Collecte d'annonces - LeBonCoin + La Centrale (Workflow WF-04).

LBC         : session Patchright avec profil persistant (compte ACTIF).
              Extraction heuristique depuis la page rendue, sans dependre
              d'une API privee ni de selecteurs DOM fixes.
La Centrale : crawl4ai AsyncWebCrawler + JsonCssExtractionStrategy.

Format unifie de sortie : RawListing
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import sentry_sdk

from app.models import ListingSource
from app.services.account_creation import _launch_patchright_context
from app.services.phone_extractor import extract_phone

log = logging.getLogger(__name__)

_LC_SCHEMA = {
    "name": "Annonces La Centrale",
    "baseSelector": "article.listing-item, div[class*='AdCard'], div[class*='listing-card']",
    "fields": [
        {"name": "title", "selector": "h2, h3, [class*='title']", "type": "text"},
        {"name": "price", "selector": "[class*='price'], [class*='Price']", "type": "text"},
        {"name": "km", "selector": "[class*='mileage'], [class*='km']", "type": "text"},
        {"name": "location", "selector": "[class*='location']", "type": "text"},
        {"name": "url", "selector": "a[href]", "type": "attribute", "attribute": "href"},
    ],
}

_LBC_GENERIC_JS_EXTRACT = """
() => {
    const seen = new Set();
    const anchors = Array.from(document.querySelectorAll('a[href]'));

    return anchors
        .map((anchor) => {
            const href = anchor.href || '';
            if (!href.includes('/voitures/') || seen.has(href)) return null;
            seen.add(href);

            const card = anchor.closest('article, li, section, div');
            const text = (card?.innerText || anchor.innerText || '').trim();
            if (!text) return null;

            const lines = Array.from(
                new Set(text.split('\\n').map((line) => line.trim()).filter(Boolean))
            );
            const title =
                lines.find((line) => !/[€]/.test(line) && !/\\bkm\\b/i.test(line)) ||
                anchor.getAttribute('aria-label') ||
                anchor.textContent ||
                '';
            const price = lines.find((line) => /€/.test(line)) || '';
            const location =
                lines.find((line) => /\\b\\d{5}\\b/.test(line)) ||
                lines[lines.length - 1] ||
                '';

            return { url: href, title, price, location, text };
        })
        .filter(Boolean)
        .slice(0, 100);
}
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
    make: str | None = None
    model: str | None = None
    year: int | None = None
    fuel: str | None = None
    transmission: str | None = None


def _parse_price(text: str | None) -> int | None:
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def _parse_km(text: str | None) -> int | None:
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def _extract_attr(attributes: list[dict[str, Any]], *keys: str) -> str:
    for attr in attributes:
        if attr.get("key") in keys:
            return str(attr.get("value_label") or attr.get("value") or "")
    return ""


def _parse_year(raw: str | None) -> int | None:
    if not raw:
        return None
    try:
        return int(str(raw)[:4])
    except (ValueError, TypeError):
        return None


def _pick_lbc_title(raw_title: str, raw_text: str, location: str | None) -> str | None:
    def _looks_like_meta(line: str) -> bool:
        return "EUR" in line or "€" in line or bool(re.search(r"\bkm\b", line, re.I))

    title = raw_title.strip()
    if title and not _looks_like_meta(title) and title != location:
        return title

    for line in [part.strip() for part in raw_text.splitlines() if part.strip()]:
        if line == location or _looks_like_meta(line):
            continue
        return line
    return None


def _parse_lbc_search_items(items: list[dict[str, Any]]) -> list[RawListing]:
    results: list[RawListing] = []
    for item in items:
        url = str(item.get("url", "")).strip()
        if not url:
            continue

        raw_text = str(item.get("text", ""))
        location = str(item.get("location", "")).strip() or None
        title = _pick_lbc_title(str(item.get("title", "")), raw_text, location)

        listing = RawListing(
            source=ListingSource.LBC,
            url=url,
            title=title,
            price=_parse_price(str(item.get("price", "")) or raw_text),
            location=location,
            raw_data=json.dumps(item, ensure_ascii=False),
        )
        results.append(enrich_with_phone(listing))
    return results


def _page_url(url: str, page_number: int) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["page"] = str(page_number)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


async def scrape_lbc(search_params: dict[str, Any]) -> list[RawListing]:
    """
    Scrape LeBonCoin via Patchright avec un compte ACTIF.

    search_params : {"marque": str, "modele": str, "km_max": int, "prix_max": int}
    """
    from patchright.async_api import async_playwright
    from sqlalchemy import select

    from app.db import get_db
    from app.tables import PlatformAccount

    async with get_db() as db:
        result = await db.execute(
            select(PlatformAccount)
            .where(
                PlatformAccount.deleted_at.is_(None),
                PlatformAccount.status == "ACTIF",
                PlatformAccount.session_path.isnot(None),
            )
            .order_by(PlatformAccount.derniere_action.asc().nullslast())
            .limit(1)
        )
        account = result.scalar_one_or_none()

    if not account:
        log.warning("scrape_lbc : aucun compte ACTIF avec session_path disponible")
        sentry_sdk.capture_message(
            "scrape_lbc called without any ACTIF account with session_path",
            level="warning",
        )
        return []

    marque = search_params.get("marque", "")
    modele = search_params.get("modele", "")
    km_max = search_params.get("km_max", 150000)
    prix_max = search_params.get("prix_max", 50000)
    region = search_params.get("region", "")
    department = search_params.get("department", "")

    search_url = (
        f"https://www.leboncoin.fr/voitures/offres/?q={marque}+{modele}"
        f"&mileage_max={km_max}&price_max={prix_max}&sort=time&order=desc"
        f"&locations={department or region}"
    )

    max_pages = max(1, min(int(search_params.get("max_pages", 50)), 100))
    raw_items: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    async with async_playwright() as p:
        ctx = await _launch_patchright_context(p.chromium, account.session_path)
        try:
            page = await ctx.new_page()
            start_page = max(1, int(search_params.get("start_page", 1)))
            for page_number in range(start_page, max_pages + 1):
                await page.goto(
                    _page_url(search_url, page_number),
                    wait_until="networkidle",
                    timeout=30_000,
                )
                page_items = await page.evaluate(_LBC_GENERIC_JS_EXTRACT, isolated_context=True)
                new_items = [item for item in page_items if item.get("url") not in seen_urls]
                if not new_items:
                    break
                raw_items.extend(new_items)
                seen_urls.update(str(item["url"]) for item in new_items)
        except Exception as exc:
            log.error("scrape_lbc heuristique echouee : %s", exc)
            sentry_sdk.capture_exception(exc)
        finally:
            await ctx.close()

    listings = _parse_lbc_search_items(raw_items)
    log.info(
        "scrape_lbc heuristique : %d annonces (compte=%s)",
        len(listings),
        account.id,
    )
    if not listings:
        sentry_sdk.capture_message(
            f"scrape_lbc returned no listing candidates for account {account.id}",
            level="warning",
        )
    return listings


async def scrape_la_centrale(search_params: dict[str, Any]) -> list[RawListing]:
    """
    Scrape La Centrale via crawl4ai + JsonCssExtractionStrategy.

    search_params : {"marque": str, "modele": str, "km_max": int, "prix_max": int}
    """
    from crawl4ai import (  # noqa: I001
        AsyncWebCrawler,
        BrowserConfig,
        CacheMode,
        CrawlerRunConfig,
        JsonCssExtractionStrategy,
    )

    marque = search_params.get("marque", "")
    modele = search_params.get("modele", "")
    km_max = search_params.get("km_max", 150000)
    prix_max = search_params.get("prix_max", 50000)

    makes_models = f"{marque.lower()}%3A{modele.lower()}"
    search_url = (
        f"https://www.lacentrale.fr/listing"
        f"?makesModelsCommercialNames={makes_models}"
        f"&mileageMax={km_max}&priceMax={prix_max}"
        f"&region={search_params.get('region', '')}"
        f"&department={search_params.get('department', '')}"
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
    seen_urls: set[str] = set()
    max_pages = max(1, min(int(search_params.get("max_pages", 50)), 100))
    async with AsyncWebCrawler(config=browser_config) as crawler:
        start_page = max(1, int(search_params.get("start_page", 1)))
        for page_number in range(start_page, max_pages + 1):
            result = await crawler.arun(
                url=_page_url(search_url, page_number), config=crawler_config
            )
            if not result.success or not result.extracted_content:
                break
            added = 0
            for item in json.loads(result.extracted_content):
                raw_url = item.get("url", "")
                if raw_url and not raw_url.startswith("http"):
                    raw_url = f"https://www.lacentrale.fr{raw_url}"
                if not raw_url or raw_url in seen_urls:
                    continue
                seen_urls.add(raw_url)
                added += 1
                listings.append(
                    enrich_with_phone(
                        RawListing(
                            source=ListingSource.LA_CENTRALE,
                            url=raw_url,
                            title=item.get("title", "").strip() or None,
                            price=_parse_price(item.get("price", "")),
                            km=_parse_km(item.get("km", "")),
                            location=item.get("location", "").strip() or None,
                            raw_data=json.dumps(item, ensure_ascii=False),
                        )
                    )
                )
            if added == 0:
                break

    log.info("scrape_la_centrale : %d annonces collectees", len(listings))
    return listings


def enrich_with_phone(listing: RawListing) -> RawListing:
    """Extrait le numero de telephone depuis le texte si absent."""
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
        make=listing.make,
        model=listing.model,
        year=listing.year,
        fuel=listing.fuel,
        transmission=listing.transmission,
    )
