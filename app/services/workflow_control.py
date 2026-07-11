from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.db import get_db
from app.models import CampaignStatus, WorkflowRunView, WorkflowStatus
from app.tables import AuditEvent, Campaign, PlatformAccount, WorkflowRun

_TRANSITIONS = {
    (WorkflowStatus.RUNNING, "pause"): WorkflowStatus.PAUSED,
    (WorkflowStatus.PENDING, "pause"): WorkflowStatus.PAUSED,
    (WorkflowStatus.PAUSED, "resume"): WorkflowStatus.PENDING,
    (WorkflowStatus.RUNNING, "cancel"): WorkflowStatus.CANCELLED,
    (WorkflowStatus.PENDING, "cancel"): WorkflowStatus.CANCELLED,
    (WorkflowStatus.PAUSED, "cancel"): WorkflowStatus.CANCELLED,
    (WorkflowStatus.FAILED, "retry"): WorkflowStatus.PENDING,
    (WorkflowStatus.CANCELLED, "retry"): WorkflowStatus.PENDING,
}


def workflow_transition(current: str, action: str) -> WorkflowStatus:
    try:
        return _TRANSITIONS[(WorkflowStatus(current), action)]
    except (ValueError, KeyError) as exc:
        raise ValueError(f"Invalid workflow transition: {current}.{action}") from exc


async def list_workflows(limit: int = 100) -> list[WorkflowRunView]:
    async with get_db() as db:
        rows = (
            await db.scalars(
                select(WorkflowRun)
                .order_by(WorkflowRun.created_at.desc())
                .limit(limit)
            )
        ).all()
    return [WorkflowRunView.model_validate(row) for row in rows]


async def command_workflow(
    *, workflow_id: UUID, action: str, idempotency_key: str, actor: str, role: str
) -> WorkflowRunView:
    async with get_db() as db:
        duplicate = await db.scalar(
            select(AuditEvent).where(AuditEvent.idempotency_key == idempotency_key)
        )
        workflow = await db.get(WorkflowRun, workflow_id)
        if workflow is None:
            raise LookupError("Workflow not found")
        if duplicate:
            return WorkflowRunView.model_validate(workflow)
        next_status = workflow_transition(workflow.status, action)
        workflow.status = next_status
        workflow.last_error = None if action == "retry" else workflow.last_error
        if next_status == WorkflowStatus.CANCELLED:
            workflow.finished_at = datetime.now(UTC)
        if workflow.workflow_type.startswith("campaign.") and workflow.target_id:
            campaign = await db.get(Campaign, UUID(workflow.target_id))
            if campaign:
                campaign.status = {
                    WorkflowStatus.PAUSED: CampaignStatus.PAUSED,
                    WorkflowStatus.CANCELLED: CampaignStatus.CANCELLED,
                    WorkflowStatus.PENDING: CampaignStatus.RUNNING,
                }.get(next_status, campaign.status)
        db.add(AuditEvent(
            actor=actor, role=role, action=f"workflow.{action}",
            target_type="workflow", target_id=str(workflow_id),
            idempotency_key=idempotency_key, input_summary={"action": action},
            result_status=next_status.value.lower(), workflow_run_id=workflow_id,
        ))
        snapshot = {
            "type": workflow.workflow_type,
            "target": workflow.target_id,
            "checkpoint": workflow.checkpoint or {},
            "celery_task_id": workflow.celery_task_id,
        }

    if action in {"pause", "cancel"}:
        await _stop_execution(workflow_id, snapshot, pause=action == "pause")
    elif action in {"resume", "retry"}:
        task_id = await _dispatch(workflow_id, snapshot)
        async with get_db() as db:
            workflow = await db.get(WorkflowRun, workflow_id)
            workflow.celery_task_id = task_id
            workflow.finished_at = None
    async with get_db() as db:
        workflow = await db.get(WorkflowRun, workflow_id)
        return WorkflowRunView.model_validate(workflow)


async def _stop_execution(workflow_id: UUID, snapshot: dict, *, pause: bool) -> None:
    workflow_type = snapshot["type"]
    if workflow_type == "browser_use.task":
        from app.config import get_settings
        from app.services.browser_use_cloud import BrowserUseCloudClient

        provider_id = snapshot["checkpoint"].get("provider_task_id")
        if provider_id:
            await BrowserUseCloudClient(get_settings().browser_use_api_key).stop_task(provider_id)
    celery_task_id = snapshot.get("celery_task_id")
    if celery_task_id:
        from app.tasks import celery_app

        celery_app.control.revoke(celery_task_id, terminate=not pause, signal="SIGTERM")


async def _dispatch(workflow_id: UUID, snapshot: dict) -> str:
    workflow_type = snapshot["type"]
    target = snapshot["target"]
    checkpoint = snapshot["checkpoint"]
    if workflow_type == "campaign.sms":
        from app.tasks import run_campaign_task

        return run_campaign_task.apply_async(args=[target, str(workflow_id)]).id
    if workflow_type == "campaign.lbc_message":
        from app.tasks import run_lbc_message_campaign_task

        return run_lbc_message_campaign_task.apply_async(
            args=[target, str(workflow_id)]
        ).id
    if workflow_type == "browser_use.task":
        from app.tasks import run_browser_use_task

        return run_browser_use_task.apply_async(args=[
            str(workflow_id), checkpoint["template_id"], target, None,
        ]).id
    if workflow_type == "experimental.lab":
        from app.tasks import run_experimental_lab_task

        return run_experimental_lab_task.apply_async(args=[
            str(workflow_id), checkpoint["engine"], target,
        ]).id
    if workflow_type == "messaging.inbox_sync":
        from app.tasks import sync_lbc_inbox_task

        return sync_lbc_inbox_task.apply_async(args=[str(workflow_id)]).id
    if workflow_type == "account.inspect":
        from app.tasks import inspect_account_task

        async with get_db() as db:
            account = await db.get(PlatformAccount, UUID(target))
        if account is None or not account.browser_use_profile_id:
            raise ValueError("Account Browser Use profile is unavailable")
        return inspect_account_task.apply_async(args=[
            str(workflow_id), target, account.browser_use_profile_id,
        ]).id
    raise ValueError(f"Workflow type cannot be dispatched: {workflow_type}")
