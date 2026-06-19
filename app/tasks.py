"""
Tâches Celery — exécutées en arrière-plan.
"""
import asyncio
import logging

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()
log = logging.getLogger(__name__)

celery_app = Celery(
    "autotransfert_p2",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Paris",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        # WF-04 — scraping quotidien à 06h00
        "scrape-lbc-daily": {
            "task": "app.tasks.scrape_listings_task",
            "schedule": crontab(hour=6, minute=0),
        },
        # Vérification pool comptes — toutes les heures
        "check-account-pool": {
            "task": "app.tasks.check_account_pool_task",
            "schedule": 3600.0,
        },
    },
)


def _run(coro):
    """Exécute une coroutine depuis un contexte synchrone Celery."""
    return asyncio.run(coro)


@celery_app.task(name="app.tasks.create_account_task", bind=True, max_retries=2)
def create_account_task(self, mode: str = "A"):
    """WF-01 — création d'un nouveau compte LBC."""
    from app.services.account_creation import (
        AccountCreationError,
        create_lbc_account,
        ProxyUnavailableError,
    )
    try:
        result = _run(create_lbc_account(mode=mode))
        log.info("Compte créé : %s", result.account_id)
        return {"account_id": result.account_id, "email": result.email}
    except ProxyUnavailableError as exc:
        log.error("Proxy 4G indisponible : %s — pas de retry (règle R07)", exc)
        raise
    except AccountCreationError as exc:
        log.warning("Échec création compte : %s — retry %d/2", exc, self.request.retries)
        raise self.retry(countdown=60, exc=exc)


@celery_app.task(name="app.tasks.run_campaign_task", bind=True)
def run_campaign_task(self, campaign_id: str):
    """WF-02 — exécution d'une campagne SMS."""
    from app.services.campaign_runner import run_campaign
    return _run(run_campaign(campaign_id))


@celery_app.task(name="app.tasks.scrape_listings_task")
def scrape_listings_task(search_params: dict | None = None):
    """WF-04 — scraping quotidien LBC + La Centrale + persistance."""
    from app.services.listing_persistence import persist_listings
    from app.services.scraper import scrape_la_centrale, scrape_lbc

    params = search_params or {}
    lbc_results = _run(scrape_lbc(params))
    lc_results = _run(scrape_la_centrale(params))
    all_listings = lbc_results + lc_results

    persist_result = _run(persist_listings(all_listings))
    log.info(
        "Scraping terminé — LBC: %d La Centrale: %d persistés: %s",
        len(lbc_results), len(lc_results), persist_result,
    )
    return {
        "lbc": len(lbc_results),
        "la_centrale": len(lc_results),
        "persist": persist_result,
    }


@celery_app.task(name="app.tasks.analyze_batch_task")
def analyze_batch_task(listing_ids: list[str]):
    """Analyse un lot d'annonces — lancé par POST /analyzer/run/batch."""
    import uuid

    from app.services.vehicle_analyzer import analyze_listing

    results = {"done": 0, "failed": 0}
    for raw_id in listing_ids:
        try:
            _run(analyze_listing(uuid.UUID(raw_id)))
            results["done"] += 1
        except Exception as exc:
            log.warning("analyze_batch_task : échec listing %s — %s", raw_id, exc)
            results["failed"] += 1

    log.info("analyze_batch_task terminé : %s", results)
    return results


@celery_app.task(name="app.tasks.check_account_pool_task")
def check_account_pool_task():
    """Vérifie le pool de comptes ACTIFS — warm-up + création si nécessaire."""
    from app.services.account_creation import _check_active_pool_needs_account
    from app.services.warm_up import evaluate_warmup_batch

    # Évalue d'abord les comptes EN_CHAUFFE avant de mesurer le pool
    warmup_result = _run(evaluate_warmup_batch())
    log.info("Warm-up évalué : %s", warmup_result)

    needs_account = _run(_check_active_pool_needs_account())
    if needs_account:
        log.info("Pool comptes sous le minimum — déclenchement création Mode A")
        create_account_task.delay(mode="A")
    return {"warmup": warmup_result, "triggered": needs_account}
