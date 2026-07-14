"""
Tâches Celery — exécutées en arrière-plan.
"""

import asyncio
import logging
from datetime import datetime

from celery import Celery

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
    task_routes={
        "app.tasks.collect_sector_task": {"queue": "collection"},
        "app.tasks.sync_lbc_inbox_task": {"queue": "inbox"},
    },
    beat_schedule={
        # WF-04 — scraping quotidien à 06h00
        "scrape-lbc-daily": {
            "task": "app.tasks.dispatch_sector_collections_task",
            "schedule": 300.0,
        },
        # Vérification pool comptes — toutes les heures
        "check-account-pool": {
            "task": "app.tasks.check_account_pool_task",
            "schedule": 3600.0,
        },
        "reconcile-account-creation-workflows": {
            "task": "app.tasks.reconcile_account_creation_workflows_task",
            "schedule": 60.0,
        },
        "refresh-connector-status": {
            "task": "app.tasks.refresh_connector_status_task",
            "schedule": 60.0,
        },
        "sync-lbc-inbox": {
            "task": "app.tasks.sync_lbc_inbox_task",
            "schedule": 600.0,
        },
        "run-sms-sequences": {
            "task": "app.tasks.run_sms_sequences_task",
            "schedule": 300.0,
        },
        "replay-sms-events": {
            "task": "app.tasks.replay_sms_events_task",
            "schedule": 60.0,
        },
    },
)


def _run(coro):
    """Exécute une coroutine depuis un contexte synchrone Celery."""

    async def run_and_dispose():
        # Celery prefork reuses a process while asyncio.run creates a new loop
        # for every task. Dispose the async DB pool before that loop disappears
        # so pooled connections are never reused by a different event loop.
        from app.db import engine

        try:
            return await coro
        finally:
            await engine.dispose()

    return asyncio.run(run_and_dispose())


@celery_app.task(name="app.tasks.create_account_task", bind=True, max_retries=2)
def create_account_task(self, mode: str = "B", workflow_id: str | None = None):
    """WF-01 — création d'un nouveau compte LBC."""
    from app.services.account_creation import (
        AccountCreationError,
        ProxyUnavailableError,
        create_lbc_account,
    )

    try:
        if workflow_id:
            from app.services.account_control import update_account_creation_workflow

            _run(update_account_creation_workflow(
                workflow_id,
                checkpoint={"stage": "started", "mode": mode},
            ))
        result = _run(create_lbc_account(mode=mode, workflow_id=workflow_id))
        if workflow_id:
            from app.services.account_control import finish_account_creation_workflow

            _run(finish_account_creation_workflow(workflow_id, str(result.account_id)))
        log.info("Compte créé : %s", result.account_id)
        return {"account_id": result.account_id, "email": result.email}
    except ProxyUnavailableError as exc:
        if workflow_id:
            from app.services.account_control import finish_account_creation_workflow

            _run(finish_account_creation_workflow(workflow_id, None, str(exc)[:500]))
        log.error("Proxy 4G indisponible : %s — pas de retry (règle R07)", exc)
        raise
    except AccountCreationError as exc:
        if workflow_id and self.request.retries < self.max_retries:
            from app.services.account_control import update_account_creation_workflow

            _run(update_account_creation_workflow(
                workflow_id,
                checkpoint={
                    "stage": "retry_scheduled",
                    "mode": mode,
                    "retry": self.request.retries + 1,
                    "error": str(exc)[:400],
                },
            ))
        if workflow_id and self.request.retries >= self.max_retries:
            from app.services.account_control import finish_account_creation_workflow

            _run(finish_account_creation_workflow(workflow_id, None, str(exc)[:500]))
        log.warning("Échec création compte : %s — retry %d/2", exc, self.request.retries)
        raise self.retry(countdown=60, exc=exc)
    except Exception as exc:
        # Configuration/provider errors (for example missing iproxy or a
        # rejected OTP provider request) must not leave the workflow pending.
        if workflow_id:
            from app.services.account_control import finish_account_creation_workflow

            _run(finish_account_creation_workflow(workflow_id, None, str(exc)[:500]))
        log.exception("Échec inattendu création compte : %s", exc)
        raise


@celery_app.task(name="app.tasks.reconcile_account_creation_workflows_task")
def reconcile_account_creation_workflows_task():
    """Closes account-creation workflows that were lost before task execution."""
    from app.services.account_control import reconcile_account_creation_workflows

    return _run(reconcile_account_creation_workflows())


@celery_app.task(name="app.tasks.run_campaign_task", bind=True)
def run_campaign_task(self, campaign_id: str, workflow_id: str | None = None):
    """WF-02 — exécution d'une campagne SMS."""
    from app.services.campaign_runner import run_campaign

    result = _run(run_campaign(campaign_id, workflow_id))
    task_args = [campaign_id, workflow_id] if workflow_id else [campaign_id]
    scheduled_for = result.get("scheduled_for")
    if result.get("status") == "deferred" and scheduled_for:
        eta = datetime.fromisoformat(scheduled_for)
        log.info("Campagne %s requeuee pour %s", campaign_id, scheduled_for)
        run_campaign_task.apply_async(args=task_args, eta=eta)
    elif result.get("status") == "running":
        log.info("Campagne %s - lot termine, relance du lot suivant", campaign_id)
        run_campaign_task.apply_async(args=task_args)
    return result


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
        len(lbc_results),
        len(lc_results),
        persist_result,
    )
    return {
        "lbc": len(lbc_results),
        "la_centrale": len(lc_results),
        "persist": persist_result,
    }


@celery_app.task(name="app.tasks.collect_sector_task", bind=True, max_retries=2)
def collect_sector_task(self, sector_id: str):
    """Collecte isolée d'un secteur : une panne ne bloque pas les autres."""
    from uuid import UUID

    from app.services.sector_collection import collect_sector

    try:
        return _run(collect_sector(UUID(sector_id)))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@celery_app.task(name="app.tasks.dispatch_sector_collections_task")
def dispatch_sector_collections_task():
    """Distribue les secteurs actifs dans des tâches indépendantes."""
    from sqlalchemy import select

    from app.db import get_db
    from app.tables import Sector

    async def list_active():
        async with get_db() as db:
            return [
                str(row.id)
                for row in (
                    await db.execute(select(Sector.id).where(Sector.status == "actif"))
                ).all()
            ]

    sector_ids = _run(list_active())
    for sector_id in sector_ids:
        collect_sector_task.delay(sector_id)
    return {"dispatched": len(sector_ids), "sector_ids": sector_ids}


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


@celery_app.task(name="app.tasks.refresh_connector_status_task")
def refresh_connector_status_task():
    """Actualise les checks read-only affiches dans le dashboard."""
    from app.services.connector_monitor import refresh_connector_statuses

    results = _run(refresh_connector_statuses())
    return [result.model_dump(mode="json") for result in results]


@celery_app.task(name="app.tasks.run_browser_use_task", bind=True, max_retries=2)
def run_browser_use_task(
    self,
    workflow_id: str,
    template_id: str,
    target_url: str,
    custom_prompt: str | None = None,
):
    """Execute une tache Browser Use bornee et persistante."""
    from uuid import UUID

    import httpx

    from app.services.browser_use_workflows import execute_browser_use_workflow

    try:
        return _run(
            execute_browser_use_workflow(UUID(workflow_id), template_id, target_url, custom_prompt)
        )
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@celery_app.task(name="app.tasks.run_experimental_lab_task")
def run_experimental_lab_task(workflow_id: str, engine: str, target_url: str):
    from uuid import UUID

    from app.services.experimental_lab import execute_lab_run

    return _run(execute_lab_run(UUID(workflow_id), engine, target_url))


@celery_app.task(name="app.tasks.run_lbc_message_campaign_task")
def run_lbc_message_campaign_task(campaign_id: str, workflow_id: str):
    """Traite toutes les annonces LBC eligibles par lots bornes."""
    from app.services.lbc_messaging import (
        mark_lbc_message_campaign_failed,
        run_lbc_message_campaign,
    )

    try:
        result = _run(run_lbc_message_campaign(campaign_id, workflow_id))
    except Exception as exc:
        # A Celery exception otherwise leaves the UI campaign as RUNNING while
        # its workflow remains PENDING, which hides the actual failure.
        _run(mark_lbc_message_campaign_failed(campaign_id, workflow_id, str(exc)))
        raise
    if result.get("status") == "running":
        run_lbc_message_campaign_task.apply_async(args=[campaign_id, workflow_id])
    return result


@celery_app.task(name="app.tasks.sync_lbc_inbox_task")
def sync_lbc_inbox_task(workflow_id: str | None = None):
    """Synchronise periodiquement les messages entrants Leboncoin."""
    from app.services.lbc_messaging import sync_lbc_inbox

    return _run(sync_lbc_inbox(workflow_id))


@celery_app.task(name="app.tasks.run_sms_sequences_task")
def run_sms_sequences_task():
    """Envoie une seule étape due par séquence, avec verrouillage DB."""
    from app.services.sms_sequence import run_due_sms_sequences

    return _run(run_due_sms_sequences())


@celery_app.task(name="app.tasks.replay_sms_events_task")
def replay_sms_events_task():
    from app.services.sms_inbox import replay_pending_sms_events

    return _run(replay_pending_sms_events())


@celery_app.task(name="app.tasks.inspect_account_task")
def inspect_account_task(workflow_id: str, account_id: str, profile_id: str):
    from uuid import UUID

    from app.services.account_control import inspect_account

    return _run(inspect_account(UUID(workflow_id), UUID(account_id), profile_id))
