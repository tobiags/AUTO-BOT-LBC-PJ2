from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.db import get_db
from app.models import (
    CampaignCommandResponse,
    CampaignOut,
    CampaignStatus,
    VehicleSearchCriteria,
    WorkflowStatus,
)
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


async def create_controlled_campaign(
    *,
    campaign_type: str,
    message_template: str,
    quota_per_sim: int,
    search_criteria: VehicleSearchCriteria,
    idempotency_key: str,
    actor: str,
    role: str,
) -> CampaignOut:
    async with get_db() as db:
        duplicate = await db.scalar(
            select(AuditEvent).where(AuditEvent.idempotency_key == idempotency_key)
        )
        if duplicate is not None and duplicate.target_id:
            campaign = await db.get(Campaign, UUID(duplicate.target_id))
            if campaign is not None:
                return CampaignOut.model_validate(campaign)
        campaign = Campaign(
            type=campaign_type,
            message_template=message_template,
            quota_per_sim=quota_per_sim,
            search_criteria=search_criteria.model_dump(exclude_none=True),
        )
        db.add(campaign)
        await db.flush()
        db.add(
            AuditEvent(
                actor=actor,
                role=role,
                action="campaign.create",
                target_type="campaign",
                target_id=str(campaign.id),
                idempotency_key=idempotency_key,
                input_summary={
                    "type": campaign_type,
                    "quota_per_sim": quota_per_sim,
                    "search_criteria": search_criteria.model_dump(exclude_none=True),
                },
                result_status="created",
            )
        )
        return CampaignOut.model_validate(campaign)


def campaign_transition(current: str, action: str) -> CampaignStatus:
    try:
        current_status = CampaignStatus(current)
        return _TRANSITIONS[(current_status, action)]
    except (ValueError, KeyError) as exc:
        raise ValueError(f"Invalid campaign transition: {current}.{action}") from exc


async def execute_campaign_command(
    *,
    campaign_id: UUID,
    action: str,
    idempotency_key: str,
    actor: str,
    role: str,
) -> CampaignCommandResponse:
    dispatch_workflow_ids: list[tuple[str, UUID]] = []
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
        workflow_types = (
            ["campaign.lbc_message", "campaign.sms"]
            if campaign.type == "both"
            else ["campaign.lbc_message" if campaign.type == "lbc_message" else "campaign.sms"]
        )
        campaign.status = next_status
        campaign.last_error = None
        workflows: list[tuple[str, WorkflowRun]] = []
        for index, workflow_type in enumerate(workflow_types):
            active = await db.scalar(
                select(WorkflowRun)
                .where(
                    WorkflowRun.workflow_type == workflow_type,
                    WorkflowRun.target_id == str(campaign_id),
                    WorkflowRun.status.in_(
                        [WorkflowStatus.PENDING, WorkflowStatus.RUNNING, WorkflowStatus.PAUSED]
                    ),
                )
                .order_by(WorkflowRun.created_at.desc())
            )
            workflow = active
            if action in {"start", "retry"} or workflow is None:
                workflow = WorkflowRun(
                    idempotency_key=f"{idempotency_key}-{index}",
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
            workflows.append((workflow_type, workflow))

        db.add(
            AuditEvent(
                actor=actor,
                role=role,
                action=f"campaign.{action}",
                target_type="campaign",
                target_id=str(campaign_id),
                idempotency_key=idempotency_key,
                input_summary={"action": action},
                result_status=next_status.value.lower(),
                workflow_run_id=workflows[0][1].id,
            )
        )
        if action in {"start", "resume", "retry"}:
            dispatch_workflow_ids = [
                (workflow_type, workflow.id) for workflow_type, workflow in workflows
            ]
        workflow_id = workflows[0][1].id

    for workflow_type, dispatch_workflow_id in dispatch_workflow_ids:
        if workflow_type == "campaign.lbc_message":
            from app.tasks import run_lbc_message_campaign_task

            task = run_lbc_message_campaign_task.apply_async(
                args=[str(campaign_id), str(dispatch_workflow_id)]
            )
        else:
            from app.tasks import run_campaign_task

            task = run_campaign_task.apply_async(args=[str(campaign_id), str(dispatch_workflow_id)])
        async with get_db() as db:
            workflow = await db.get(WorkflowRun, dispatch_workflow_id)
            workflow.celery_task_id = task.id

    return CampaignCommandResponse(
        campaign_id=campaign_id,
        workflow_id=workflow_id,
        status=next_status,
        action=action,
    )
