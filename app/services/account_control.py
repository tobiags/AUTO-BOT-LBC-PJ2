import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select

from app.config import get_settings
from app.db import get_db
from app.models import AccountCommandResponse, AccountStatus, WorkflowStatus
from app.services.browser_use_cloud import BrowserUseCloudClient
from app.tables import AuditEvent, PlatformAccount, WorkflowRun

_TRANSITIONS = {
    (AccountStatus.ACTIF, "quarantine"): AccountStatus.QUARANTAINE,
    (AccountStatus.RALENTI, "quarantine"): AccountStatus.QUARANTAINE,
    (AccountStatus.BLOQUE, "quarantine"): AccountStatus.QUARANTAINE,
    (AccountStatus.EN_CHAUFFE, "quarantine"): AccountStatus.QUARANTAINE,
    (AccountStatus.EN_CREATION, "quarantine"): AccountStatus.QUARANTAINE,
    (AccountStatus.QUARANTAINE, "restore"): AccountStatus.EN_CHAUFFE,
    (AccountStatus.BLOQUE, "restore"): AccountStatus.EN_CHAUFFE,
    (AccountStatus.EN_CREATION, "warm"): AccountStatus.EN_CHAUFFE,
    (AccountStatus.RALENTI, "warm"): AccountStatus.EN_CHAUFFE,
}


def account_transition(current: str, action: str) -> AccountStatus:
    try:
        return _TRANSITIONS[(AccountStatus(current), action)]
    except (ValueError, KeyError) as exc:
        raise ValueError(f"Invalid account transition: {current}.{action}") from exc


async def execute_account_command(
    *, account_id: UUID, action: str, idempotency_key: str, actor: str, role: str
) -> AccountCommandResponse:
    async with get_db() as db:
        duplicate = await db.scalar(
            select(AuditEvent).where(AuditEvent.idempotency_key == idempotency_key)
        )
        if duplicate:
            return AccountCommandResponse(
                account_id=account_id,
                workflow_id=duplicate.workflow_run_id,
                action=action,
                status=duplicate.result_status,
            )
        account = await db.get(PlatformAccount, account_id)
        if account is None:
            raise LookupError("Account not found")
        if action == "inspect" and not account.browser_use_profile_id:
            raise ValueError("Account has no Browser Use profile")
        workflow = WorkflowRun(
            idempotency_key=idempotency_key,
            workflow_type=f"account.{action}",
            target_type="account",
            target_id=str(account_id),
            status=WorkflowStatus.PENDING,
            initiated_by=actor,
        )
        db.add(workflow)
        await db.flush()
        if action != "inspect":
            account.status = account_transition(account.status, action)
            account.derniere_action = datetime.now(UTC)
            workflow.status = WorkflowStatus.COMPLETED
            workflow.finished_at = datetime.now(UTC)
        db.add(AuditEvent(
            actor=actor, role=role, action=f"account.{action}",
            target_type="account", target_id=str(account_id),
            idempotency_key=idempotency_key, input_summary={"action": action},
            result_status=workflow.status.value.lower(), workflow_run_id=workflow.id,
        ))
        workflow_id = workflow.id
        profile_id = account.browser_use_profile_id

    if action == "inspect":
        from app.tasks import inspect_account_task

        task = inspect_account_task.delay(str(workflow_id), str(account_id), profile_id)
        async with get_db() as db:
            workflow = await db.get(WorkflowRun, workflow_id)
            workflow.celery_task_id = task.id
    elif action == "warm":
        from app.tasks import check_account_pool_task

        check_account_pool_task.delay()
    return AccountCommandResponse(
        account_id=account_id,
        workflow_id=workflow_id,
        action=action,
        status="queued" if action == "inspect" else "completed",
    )


async def create_account_command(
    *, mode: str, idempotency_key: str, actor: str, role: str
) -> AccountCommandResponse:
    async with get_db() as db:
        existing = await db.scalar(
            select(WorkflowRun).where(WorkflowRun.idempotency_key == idempotency_key)
        )
        if existing:
            return AccountCommandResponse(
                account_id=None, workflow_id=existing.id,
                action="create", status=existing.status.value.lower(),
            )
        workflow = WorkflowRun(
            idempotency_key=idempotency_key,
            workflow_type="account.create",
            target_type="account_pool",
            target_id=mode,
            status=WorkflowStatus.PENDING,
            initiated_by=actor,
        )
        db.add(workflow)
        await db.flush()
        db.add(AuditEvent(
            actor=actor, role=role, action="account.create",
            target_type="account_pool", target_id=mode,
            idempotency_key=idempotency_key, input_summary={"mode": mode},
            result_status="queued", workflow_run_id=workflow.id,
        ))
        workflow_id = workflow.id
    from app.tasks import create_account_task
    try:
        task = create_account_task.delay(mode=mode, workflow_id=str(workflow_id))
        async with get_db() as db:
            workflow = await db.get(WorkflowRun, workflow_id)
            workflow.celery_task_id = task.id
    except Exception as exc:
        # Do not leave an invisible PENDING workflow when the broker is down
        # or Celery rejects the dispatch before returning a task id.
        await finish_account_creation_workflow(
            str(workflow_id), None, f"Account creation dispatch failed: {str(exc)[:400]}"
        )
        raise
    return AccountCommandResponse(
        account_id=None, workflow_id=workflow_id, action="create", status="queued"
    )


async def inspect_account(
    workflow_id: UUID, account_id: UUID, profile_id: str
) -> dict:
    settings = get_settings()
    client = BrowserUseCloudClient(settings.browser_use_api_key)
    async with get_db() as db:
        workflow = await db.get(WorkflowRun, workflow_id)
        workflow.status = WorkflowStatus.RUNNING
        workflow.started_at = datetime.now(UTC)
    task = await client.create_task(
        task=(
            "Controle la session du compte Leboncoin, les alertes visibles et "
            "la disponibilite de la messagerie. Ne modifie rien."
        ),
        metadata={"template": "account_diagnostic", "account_id": str(account_id)},
        allowed_domains=("leboncoin.fr", "www.leboncoin.fr"),
        session_settings={"profileId": profile_id, "proxyCountryCode": "FR"},
    )
    task_id = task.get("id") or task.get("taskId")
    elapsed = 0
    while elapsed < settings.browser_use_task_timeout_seconds:
        status = await client.get_task_status(task_id)
        if status.get("status") in {"finished", "stopped"}:
            detail = await client.get_task(task_id)
            break
        await asyncio.sleep(settings.browser_use_poll_interval_seconds)
        elapsed += settings.browser_use_poll_interval_seconds
    else:
        await client.stop_task(task_id)
        raise TimeoutError("Account inspection timed out")
    async with get_db() as db:
        workflow = await db.get(WorkflowRun, workflow_id)
        workflow.status = WorkflowStatus.COMPLETED
        workflow.checkpoint = {
            "provider_task_id": task_id,
            "session_id": task.get("sessionId"),
            "output": detail.get("output"),
            "is_success": detail.get("isSuccess"),
        }
        workflow.finished_at = datetime.now(UTC)
        account = await db.get(PlatformAccount, account_id)
        account.browser_use_session_id = task.get("sessionId")
        account.derniere_action = datetime.now(UTC)
    return detail


async def finish_account_creation_workflow(
    workflow_id: str, account_id: str | None, error: str | None = None
) -> None:
    async with get_db() as db:
        workflow = await db.get(WorkflowRun, UUID(workflow_id))
        workflow.status = WorkflowStatus.FAILED if error else WorkflowStatus.COMPLETED
        workflow.checkpoint = {
            **(workflow.checkpoint or {}),
            **({"account_id": account_id} if account_id else {}),
            **({"stage": "failed"} if error else {"stage": "completed"}),
        }
        workflow.last_error = error
        workflow.finished_at = datetime.now(UTC)


async def update_account_creation_workflow(
    workflow_id: str,
    *,
    status: WorkflowStatus = WorkflowStatus.RUNNING,
    checkpoint: dict | None = None,
) -> None:
    """Persist the current account-creation step for dashboard observability."""
    async with get_db() as db:
        workflow = await db.get(WorkflowRun, UUID(workflow_id))
        if workflow is None or workflow.workflow_type != "account.create":
            return
        workflow.status = status
        if checkpoint is not None:
            workflow.checkpoint = {**(workflow.checkpoint or {}), **checkpoint}
        if status == WorkflowStatus.RUNNING and workflow.started_at is None:
            workflow.started_at = datetime.now(UTC)


async def remove_quarantined_account(
    *, account_id: UUID, idempotency_key: str, actor: str, role: str
) -> AccountCommandResponse:
    """Remove a failed account from the active pool without destroying its audit trail."""
    async with get_db() as db:
        duplicate = await db.scalar(
            select(AuditEvent).where(AuditEvent.idempotency_key == idempotency_key)
        )
        if duplicate:
            return AccountCommandResponse(
                account_id=account_id,
                workflow_id=duplicate.workflow_run_id,
                action="delete",
                status=duplicate.result_status,
            )
        account = await db.get(PlatformAccount, account_id)
        if account is None:
            raise LookupError("Account not found")
        if account.status != AccountStatus.QUARANTAINE:
            raise ValueError("Seuls les comptes en quarantaine peuvent être supprimés")
        account.deleted_at = datetime.now(UTC)
        account.derniere_action = datetime.now(UTC)
        workflow = WorkflowRun(
            idempotency_key=idempotency_key,
            workflow_type="account.delete",
            target_type="account",
            target_id=str(account_id),
            status=WorkflowStatus.COMPLETED,
            initiated_by=actor,
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
        )
        db.add(workflow)
        await db.flush()
        db.add(AuditEvent(
            actor=actor,
            role=role,
            action="account.delete",
            target_type="account",
            target_id=str(account_id),
            idempotency_key=idempotency_key,
            input_summary={"action": "delete", "mode": "soft_delete"},
            result_status="completed",
            workflow_run_id=workflow.id,
        ))
        return AccountCommandResponse(
            account_id=account_id,
            workflow_id=workflow.id,
            action="delete",
            status="completed",
        )


async def reconcile_account_creation_workflows(
    *, pending_timeout_minutes: int = 10, running_timeout_minutes: int = 30
) -> dict[str, int]:
    """Fail account-creation workflows that no longer have a live worker."""
    now = datetime.now(UTC)
    pending_cutoff = now - timedelta(minutes=pending_timeout_minutes)
    running_cutoff = now - timedelta(minutes=running_timeout_minutes)
    reconciled = 0
    async with get_db() as db:
        workflows = (
            await db.scalars(
                select(WorkflowRun).where(
                    WorkflowRun.workflow_type == "account.create",
                    WorkflowRun.status.in_([WorkflowStatus.PENDING, WorkflowStatus.RUNNING]),
                )
            )
        ).all()
        for workflow in workflows:
            was_pending = workflow.status == WorkflowStatus.PENDING
            cutoff = pending_cutoff if was_pending else running_cutoff
            reference_time = workflow.started_at or workflow.created_at
            if reference_time is None or reference_time > cutoff:
                continue
            workflow.status = WorkflowStatus.FAILED
            workflow.last_error_code = "WORKER_TIMEOUT"
            workflow.last_error = (
                "Workflow account.create expire : aucune progression persistée "
                "depuis "
                f"{pending_timeout_minutes if was_pending else running_timeout_minutes} minutes."
            )
            workflow.checkpoint = {
                **(workflow.checkpoint or {}),
                "stage": "reconciled_timeout",
            }
            workflow.finished_at = now
            reconciled += 1
    return {"reconciled": reconciled}
