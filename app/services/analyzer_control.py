from uuid import UUID

from sqlalchemy import select

from app.db import get_db
from app.models import WorkflowRunView, WorkflowStatus
from app.tables import AuditEvent, Listing, WorkflowRun


async def queue_listing_analysis(
    *, listing_id: UUID, idempotency_key: str, actor: str, role: str,
) -> WorkflowRunView:
    async with get_db() as db:
        existing = await db.scalar(
            select(WorkflowRun).where(WorkflowRun.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return WorkflowRunView.model_validate(existing)
        if await db.get(Listing, listing_id) is None:
            raise LookupError("Listing not found")
        workflow = WorkflowRun(
            idempotency_key=idempotency_key,
            workflow_type="analyzer.listing",
            target_type="listing",
            target_id=str(listing_id),
            status=WorkflowStatus.PENDING,
            progress_total=1,
            batch_size=1,
            initiated_by=actor,
        )
        db.add(workflow)
        await db.flush()
        db.add(AuditEvent(
            actor=actor,
            role=role,
            action="analyzer.listing.queue",
            target_type="listing",
            target_id=str(listing_id),
            idempotency_key=idempotency_key,
            input_summary={},
            result_status="queued",
            workflow_run_id=workflow.id,
        ))
        workflow_id = workflow.id

    from app.tasks import analyze_batch_task

    task = analyze_batch_task.delay([str(listing_id)])
    async with get_db() as db:
        workflow = await db.get(WorkflowRun, workflow_id)
        workflow.celery_task_id = task.id
        return WorkflowRunView.model_validate(workflow)
