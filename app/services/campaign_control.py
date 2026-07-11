from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.db import get_db
from app.models import CampaignCommandResponse, CampaignStatus, WorkflowStatus
from app.tables import AuditEvent, Campaign, WorkflowRun

_TRANSITIONS = {
    (CampaignStatus.PENDING, "start"): CampaignStatus.RUNNING,
    (CampaignStatus.RUNNING, "pause"): CampaignStatus.PAUSED,
    (CampaignStatus.PAUSED, "resume"): CampaignStatus.RUNNING,
    (CampaignStatus.RUNNING, "cancel"): CampaignStatus.CANCELLED,
    (CampaignStatus.PAUSED, "cancel"): CampaignStatus.CANCELLED,
    (CampaignStatus.PENDING, "cancel"): CampaignStatus.CANCELLED,
    (CampaignStatus.FAILED, "retry"): CampaignStatus.RUNNING,
}


def campaign_transition(current: str, action: str) -> CampaignStatus:
    try:
        current_status = CampaignStatus(current)
        return _TRANSITIONS[(current_status, action)]
    except (ValueError, KeyError) as exc:
        raise ValueError(
            f"Invalid campaign transition: {current}.{action}"
        ) from exc


async def execute_campaign_command(
    *,
    campaign_id: UUID,
    action: str,
    idempotency_key: str,
    actor: str,
    role: str,
) -> CampaignCommandResponse:
    dispatch_workflow_id: UUID | None = None
    async with get_db() as db:
        duplicate = await db.scalar(
            select(AuditEvent).where(AuditEvent.idempotency_key == idempotency_key)
        )
        if duplicate is not None:
            campaign = await db.get(Campaign, campaign_id)
            return CampaignCommandResponse(
                campaign_id=campaign_id,
                workflow_id=duplicate.workflow_run_id,
                status=campaign.status,
                action=action,
            )

        campaign = await db.get(Campaign, campaign_id)
        if campaign is None:
            raise LookupError("Campaign not found")
        next_status = campaign_transition(campaign.status, action)
        workflow_type = (
            "campaign.lbc_message"
            if campaign.type == "lbc_message"
            else "campaign.sms"
        )
        campaign.status = next_status
        campaign.last_error = None

        active = await db.scalar(
            select(WorkflowRun)
            .where(
                WorkflowRun.workflow_type == workflow_type,
                WorkflowRun.target_id == str(campaign_id),
                WorkflowRun.status.in_([
                    WorkflowStatus.PENDING,
                    WorkflowStatus.RUNNING,
                    WorkflowStatus.PAUSED,
                ]),
            )
            .order_by(WorkflowRun.created_at.desc())
        )
        workflow = active
        if action in {"start", "retry"} or workflow is None:
            workflow = WorkflowRun(
                idempotency_key=idempotency_key,
                workflow_type=workflow_type,
                target_type="campaign",
                target_id=str(campaign_id),
                status=WorkflowStatus.PENDING,
                batch_size=200,
                initiated_by=actor,
            )
            db.add(workflow)
            await db.flush()
        elif action == "pause":
            workflow.status = WorkflowStatus.PAUSED
        elif action == "cancel":
            workflow.status = WorkflowStatus.CANCELLED
            workflow.finished_at = datetime.now(UTC)
        elif action == "resume":
            workflow.status = WorkflowStatus.PENDING

        db.add(AuditEvent(
            actor=actor,
            role=role,
            action=f"campaign.{action}",
            target_type="campaign",
            target_id=str(campaign_id),
            idempotency_key=idempotency_key,
            input_summary={"action": action},
            result_status=next_status.value.lower(),
            workflow_run_id=workflow.id,
        ))
        if action in {"start", "resume", "retry"}:
            dispatch_workflow_id = workflow.id
        workflow_id = workflow.id

    if dispatch_workflow_id is not None:
        if workflow_type == "campaign.lbc_message":
            from app.tasks import run_lbc_message_campaign_task

            task = run_lbc_message_campaign_task.apply_async(
                args=[str(campaign_id), str(dispatch_workflow_id)]
            )
        else:
            from app.tasks import run_campaign_task

            task = run_campaign_task.apply_async(
                args=[str(campaign_id), str(dispatch_workflow_id)]
            )
        async with get_db() as db:
            workflow = await db.get(WorkflowRun, dispatch_workflow_id)
            workflow.celery_task_id = task.id

    return CampaignCommandResponse(
        campaign_id=campaign_id,
        workflow_id=workflow_id,
        status=next_status,
        action=action,
    )
