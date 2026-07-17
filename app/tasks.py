"""
Tâches Celery — exécutées en arrière-plan.
"""

import asyncio
import hashlib
import json
import logging
import random
from datetime import datetime
from typing import Any

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
        "app.tasks.dispatch_due_apify_bindings_task": {"queue": "apify"},
        "app.tasks.launch_apify_binding_task": {"queue": "apify"},
        "app.tasks.import_apify_run_task": {"queue": "apify"},
        "app.tasks.reconcile_apify_runs_task": {"queue": "apify"},
        "app.tasks.evaluate_apify_profiles_task": {"queue": "apify"},
    },
    beat_schedule={
        # WF-04 — dispatcher toutes les 5 minutes; seuls les secteurs dus partent.
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
        "reconcile-phone-activations": {
            "task": "app.tasks.reconcile_phone_activations_task",
            "schedule": 15.0,
        },
        "purge-expired-email-messages": {
            "task": "app.tasks.purge_expired_email_messages_task",
            "schedule": 86400.0,
        },
        "dispatch-due-apify-bindings": {
            "task": "app.tasks.dispatch_due_apify_bindings_task",
            "schedule": 60.0,
        },
        "reconcile-apify-runs": {
            "task": "app.tasks.reconcile_apify_runs_task",
            "schedule": float(settings.apify_reconcile_minutes * 60),
        },
        "evaluate-apify-profiles": {
            "task": "app.tasks.evaluate_apify_profiles_task",
            "schedule": 3600.0,
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


def _retryable_apify_error(exc: Exception) -> bool:
    import httpx

    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, OSError)):
        return True
    status_code = getattr(exc, "status_code", None)
    if status_code is None:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
    return status_code == 429 or bool(status_code and status_code >= 500)


def _apify_retry_delay(retries: int) -> int:
    return 60 * (2**retries) + random.randint(0, 15)


async def _record_apify_terminal_error(
    target_type: str,
    target_id: str,
    exc: Exception,
) -> None:
    from app.db import get_db
    from app.tables import AuditEvent

    async with get_db() as db:
        db.add(
            AuditEvent(
                actor="system",
                role="admin",
                action="apify.task.failed",
                target_type=target_type,
                target_id=target_id,
                input_summary={"error_type": type(exc).__name__},
                result_status="failed",
            )
        )


def _payload_shape(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _payload_shape(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_payload_shape(value[0])] if value else []
    return type(value).__name__


def _apify_circuit_breaker_reason(
    *,
    total: int,
    actionable: int,
    ambiguities: int,
    phone_count: int,
    duplicate_count: int,
    schema_changed: bool,
) -> str | None:
    ambiguity_rate = ambiguities / total if total else 0.0
    duplicate_rate = duplicate_count / phone_count if phone_count else 0.0
    if ambiguity_rate > 0.10:
        return "ambiguous_phone_rate"
    if duplicate_rate > 0.20:
        return "duplicate_anomaly"
    if schema_changed and actionable == 0:
        return "schema_changed_without_actionable_items"
    return None


async def evaluate_apify_binding_circuit_breaker(
    account_id: str,
    remote_run_id: str,
) -> dict[str, Any]:
    from uuid import UUID

    from sqlalchemy import select

    from app.db import get_db
    from app.tables import (
        ApifyActorBinding,
        ApifyException,
        ApifyItem,
        ApifyRun,
    )

    async with get_db() as db:
        run = await db.scalar(
            select(ApifyRun).where(
                ApifyRun.account_id == UUID(account_id),
                ApifyRun.apify_run_id == remote_run_id,
            )
        )
        if run is None:
            raise LookupError("apify_run_not_found")
        binding = await db.scalar(
            select(ApifyActorBinding)
            .where(ApifyActorBinding.id == run.binding_id)
            .with_for_update()
        )
        if binding is None:
            raise LookupError("apify_binding_not_found")
        items = list(
            (
                await db.scalars(
                    select(ApifyItem)
                    .join(ApifyRun, ApifyRun.id == ApifyItem.run_id)
                    .where(ApifyRun.binding_id == binding.id)
                    .order_by(ApifyItem.created_at.desc())
                    .limit(100)
                )
            ).all()
        )
        total = len(items)
        actionable = sum(item.status == "imported" for item in items)
        ambiguities = sum(item.status == "exception" for item in items)
        phones = [
            item.normalized_payload.get("phone_e164")
            for item in items
            if item.normalized_payload and item.normalized_payload.get("phone_e164")
        ]
        duplicate_count = len(phones) - len(set(phones))
        ambiguity_rate = ambiguities / total if total else 0.0
        duplicate_rate = duplicate_count / len(phones) if phones else 0.0
        current_schema = None
        if items:
            shape = json.dumps(
                _payload_shape(items[0].raw_payload),
                sort_keys=True,
                separators=(",", ":"),
            )
            current_schema = hashlib.sha256(shape.encode()).hexdigest()
        schema_changed = bool(
            current_schema
            and binding.schema_fingerprint
            and current_schema != binding.schema_fingerprint
        )
        if current_schema and binding.schema_fingerprint is None:
            binding.schema_fingerprint = current_schema

        reason = _apify_circuit_breaker_reason(
            total=total,
            actionable=actionable,
            ambiguities=ambiguities,
            phone_count=len(phones),
            duplicate_count=duplicate_count,
            schema_changed=schema_changed,
        )
        if reason and not binding.suspended_reason:
            binding.suspended_reason = reason
            db.add(
                ApifyException(
                    workspace_id=binding.workspace_id,
                    binding_id=binding.id,
                    run_id=run.id,
                    category="binding_suspended",
                    evidence={
                        "reason": reason,
                        "sample_size": total,
                        "ambiguity_rate": round(ambiguity_rate, 4),
                        "duplicate_rate": round(duplicate_rate, 4),
                        "schema_changed": schema_changed,
                    },
                )
            )
        return {
            "binding_id": str(binding.id),
            "sample_size": total,
            "ambiguity_rate": ambiguity_rate,
            "duplicate_rate": duplicate_rate,
            "suspended": bool(binding.suspended_reason),
            "reason": binding.suspended_reason,
        }


async def _candidate_apify_profile_ids() -> list[str]:
    from sqlalchemy import select

    from app.db import get_db
    from app.tables import ApifyNormalizationProfile

    async with get_db() as db:
        return [
            str(profile_id)
            for profile_id in (
                await db.scalars(
                    select(ApifyNormalizationProfile.id).where(
                        ApifyNormalizationProfile.status == "candidate"
                    )
                )
            ).all()
        ]


@celery_app.task(name="app.tasks.dispatch_due_apify_bindings_task")
def dispatch_due_apify_bindings_task():
    from app.services.apify_runs import get_due_binding_ids

    binding_ids = _run(get_due_binding_ids())
    for binding_id in binding_ids:
        launch_apify_binding_task.delay(str(binding_id))
    return {
        "dispatched": len(binding_ids),
        "binding_ids": [str(binding_id) for binding_id in binding_ids],
    }


@celery_app.task(name="app.tasks.launch_apify_binding_task", bind=True, max_retries=3)
def launch_apify_binding_task(self, binding_id: str):
    from uuid import UUID

    from app.services.apify_runs import launch_binding

    try:
        result = _run(launch_binding(UUID(binding_id), trigger="schedule"))
        return result.model_dump(mode="json")
    except Exception as exc:
        if _retryable_apify_error(exc) and self.request.retries < self.max_retries:
            raise self.retry(
                exc=exc,
                countdown=_apify_retry_delay(self.request.retries),
            ) from exc
        _run(_record_apify_terminal_error("apify_binding", binding_id, exc))
        raise


@celery_app.task(name="app.tasks.import_apify_run_task", bind=True, max_retries=3)
def import_apify_run_task(self, account_id: str, remote_run_id: str):
    from uuid import UUID

    from app.services.apify_ingestion import import_remote_run

    try:
        result = _run(import_remote_run(UUID(account_id), remote_run_id))
        result["circuit_breaker"] = _run(
            evaluate_apify_binding_circuit_breaker(account_id, remote_run_id)
        )
        return result
    except Exception as exc:
        if _retryable_apify_error(exc) and self.request.retries < self.max_retries:
            raise self.retry(
                exc=exc,
                countdown=_apify_retry_delay(self.request.retries),
            ) from exc
        _run(
            _record_apify_terminal_error(
                "apify_run",
                remote_run_id,
                exc,
            )
        )
        raise


@celery_app.task(name="app.tasks.reconcile_apify_runs_task", bind=True, max_retries=3)
def reconcile_apify_runs_task(self):
    from app.services.apify_runs import reconcile_runs

    try:
        return _run(reconcile_runs())
    except Exception as exc:
        if _retryable_apify_error(exc) and self.request.retries < self.max_retries:
            raise self.retry(
                exc=exc,
                countdown=_apify_retry_delay(self.request.retries),
            ) from exc
        _run(_record_apify_terminal_error("apify_reconcile", "all", exc))
        raise


@celery_app.task(name="app.tasks.evaluate_apify_profiles_task")
def evaluate_apify_profiles_task():
    from uuid import UUID

    from app.services.apify_learning import evaluate_candidate

    profile_ids = _run(_candidate_apify_profile_ids())
    decisions = []
    for profile_id in profile_ids:
        try:
            experiment = _run(evaluate_candidate(UUID(profile_id)))
            decisions.append(
                {
                    "profile_id": profile_id,
                    "decision": experiment.decision.value
                    if hasattr(experiment.decision, "value")
                    else experiment.decision,
                }
            )
        except Exception as exc:
            _run(_record_apify_terminal_error("apify_profile", profile_id, exc))
            decisions.append({"profile_id": profile_id, "decision": "crash"})
    return {"evaluated": len(decisions), "decisions": decisions}


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

            _run(
                update_account_creation_workflow(
                    workflow_id,
                    checkpoint={"stage": "started", "mode": mode},
                )
            )
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
        from app.services.scraper import is_datadome_blocked

        if is_datadome_blocked(str(exc)):
            if workflow_id:
                from app.services.account_control import finish_account_creation_workflow

                _run(finish_account_creation_workflow(workflow_id, None, str(exc)[:500]))
            log.error("DataDome detecte : aucune nouvelle tentative automatique")
            raise
        if workflow_id and self.request.retries < self.max_retries:
            from app.services.account_control import update_account_creation_workflow

            _run(
                update_account_creation_workflow(
                    workflow_id,
                    checkpoint={
                        "stage": "retry_scheduled",
                        "mode": mode,
                        "retry": self.request.retries + 1,
                        "error": str(exc)[:400],
                    },
                )
            )
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
    """WF-04 — collecte LBC + La Centrale à la demande et persistance."""
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
    from app.services.sector_collection import get_due_sector_ids

    sector_ids = _run(get_due_sector_ids())
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


@celery_app.task(name="app.tasks.reconcile_phone_activations_task")
def reconcile_phone_activations_task():
    from app.services.phone_operations import reconcile_phone_activations

    return _run(reconcile_phone_activations())


@celery_app.task(name="app.tasks.purge_expired_email_messages_task")
def purge_expired_email_messages_task():
    from app.services.email_inbox import purge_expired_email_messages

    return _run(purge_expired_email_messages())


@celery_app.task(name="app.tasks.inspect_account_task")
def inspect_account_task(workflow_id: str, account_id: str, profile_id: str):
    from uuid import UUID

    from app.services.account_control import inspect_account

    return _run(inspect_account(UUID(workflow_id), UUID(account_id), profile_id))
