from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy import select

from app.config import get_settings
from app.db import get_db
from app.models import LabRunView, WorkflowStatus
from app.tables import AuditEvent, WorkflowRun


async def create_lab_run(
    *, engine: str, target_url: str, idempotency_key: str, actor: str, role: str
) -> LabRunView:
    settings = get_settings()
    if not settings.lab_api_token:
        raise ValueError("Experimental lab is not configured")
    if engine == "camoufox" and not settings.camoufox_enabled:
        raise ValueError("Camoufox is disabled")
    if engine == "obscura" and not settings.obscura_enabled:
        raise ValueError("Obscura is disabled")
    if engine == "both" and not (settings.camoufox_enabled and settings.obscura_enabled):
        raise ValueError("Both experimental engines must be enabled")

    async with get_db() as db:
        existing = await db.scalar(
            select(WorkflowRun).where(WorkflowRun.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return _view(existing)
        workflow = WorkflowRun(
            idempotency_key=idempotency_key,
            workflow_type="experimental.lab",
            target_type="url",
            target_id=target_url,
            status=WorkflowStatus.PENDING,
            initiated_by=actor,
            checkpoint={"engine": engine},
        )
        db.add(workflow)
        await db.flush()
        db.add(AuditEvent(
            actor=actor, role=role, action="experimental.lab.start",
            target_type="url", target_id=target_url,
            idempotency_key=idempotency_key,
            input_summary={"engine": engine}, result_status="queued",
            workflow_run_id=workflow.id,
        ))
        workflow_id = workflow.id

    from app.tasks import run_experimental_lab_task

    task = run_experimental_lab_task.delay(str(workflow_id), engine, target_url)
    async with get_db() as db:
        workflow = await db.get(WorkflowRun, workflow_id)
        workflow.celery_task_id = task.id
    return await get_lab_run(workflow_id)


async def execute_lab_run(workflow_id: UUID, engine: str, target_url: str) -> dict:
    settings = get_settings()
    async with get_db() as db:
        workflow = await db.get(WorkflowRun, workflow_id)
        workflow.status = WorkflowStatus.RUNNING
        workflow.started_at = datetime.now(UTC)
    endpoint = "compare" if engine == "both" else "diagnostics"
    payload = {"engine": "camoufox" if engine == "both" else engine, "url": target_url}
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                f"{settings.lab_service_url}/{endpoint}",
                json=payload,
                headers={"X-Lab-Token": settings.lab_api_token},
            )
            response.raise_for_status()
            result = response.json()
    except Exception as exc:
        async with get_db() as db:
            workflow = await db.get(WorkflowRun, workflow_id)
            workflow.status = WorkflowStatus.FAILED
            workflow.last_error = str(exc)[:500]
            workflow.finished_at = datetime.now(UTC)
        raise
    async with get_db() as db:
        workflow = await db.get(WorkflowRun, workflow_id)
        workflow.status = WorkflowStatus.COMPLETED
        workflow.checkpoint = {"engine": engine, "result": result}
        workflow.finished_at = datetime.now(UTC)
    return result


async def list_lab_runs(limit: int = 50) -> list[LabRunView]:
    async with get_db() as db:
        rows = (
            await db.scalars(
                select(WorkflowRun)
                .where(WorkflowRun.workflow_type == "experimental.lab")
                .order_by(WorkflowRun.created_at.desc())
                .limit(limit)
            )
        ).all()
    return [_view(row) for row in rows]


async def get_lab_run(workflow_id: UUID) -> LabRunView:
    async with get_db() as db:
        workflow = await db.get(WorkflowRun, workflow_id)
    if workflow is None or workflow.workflow_type != "experimental.lab":
        raise LookupError("Lab run not found")
    return _view(workflow)


async def cancel_lab_run(workflow_id: UUID) -> LabRunView:
    from app.tasks import celery_app

    async with get_db() as db:
        workflow = await db.get(WorkflowRun, workflow_id)
        if workflow is None or workflow.workflow_type != "experimental.lab":
            raise LookupError("Lab run not found")
        if workflow.celery_task_id:
            celery_app.control.revoke(workflow.celery_task_id, terminate=True, signal="SIGTERM")
        workflow.status = WorkflowStatus.CANCELLED
        workflow.finished_at = datetime.now(UTC)
    return await get_lab_run(workflow_id)


def _view(workflow: WorkflowRun) -> LabRunView:
    checkpoint = workflow.checkpoint or {}
    return LabRunView(
        workflow_id=workflow.id,
        engine=checkpoint.get("engine", "unknown"),
        target_url=workflow.target_id,
        status=workflow.status,
        result=checkpoint.get("result") or {},
        last_error=workflow.last_error,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
    )
