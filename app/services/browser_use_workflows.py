import asyncio
from datetime import UTC, datetime
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import select, update

from app.config import get_settings
from app.db import get_db
from app.models import BrowserUseTaskCreated, BrowserUseTaskView, WorkflowStatus
from app.services.browser_use_cloud import BROWSER_USE_TEMPLATES, BrowserUseCloudClient
from app.tables import AuditEvent, WorkflowRun


async def create_browser_use_workflow(
    *,
    template_id: str,
    target_url: str,
    idempotency_key: str,
    actor: str,
    role: str,
    custom_prompt: str | None = None,
) -> BrowserUseTaskCreated:
    settings = get_settings()
    if not settings.browser_use_api_key:
        raise ValueError("Browser Use Cloud is not configured")
    template = BROWSER_USE_TEMPLATES.get(template_id)
    if template is None:
        raise ValueError("Unknown Browser Use template")
    host = (urlparse(target_url).hostname or "").lower()
    if host not in template.allowed_domains:
        raise ValueError("Target domain is not allowed for this template")
    if custom_prompt and role != "admin":
        raise PermissionError("Custom Browser Use tasks require the admin role")

    async with get_db() as db:
        existing = await db.scalar(
            select(WorkflowRun).where(WorkflowRun.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return BrowserUseTaskCreated(
                workflow_id=existing.id,
                status=existing.status,
                template_id=template_id,
            )
        workflow = WorkflowRun(
            idempotency_key=idempotency_key,
            workflow_type="browser_use.task",
            target_type="url",
            target_id=target_url,
            status=WorkflowStatus.PENDING,
            initiated_by=actor,
            checkpoint={"template_id": template_id},
        )
        db.add(workflow)
        await db.flush()
        db.add(AuditEvent(
            actor=actor,
            role=role,
            action="browser_use.task.create",
            target_type="url",
            target_id=target_url,
            idempotency_key=idempotency_key,
            input_summary={"template_id": template_id, "custom": bool(custom_prompt)},
            result_status="queued",
            workflow_run_id=workflow.id,
        ))
        workflow_id = workflow.id

    from app.tasks import run_browser_use_task

    task = run_browser_use_task.delay(
        str(workflow_id), template_id, target_url, custom_prompt
    )
    async with get_db() as db:
        await db.execute(
            update(WorkflowRun)
            .where(WorkflowRun.id == workflow_id)
            .values(celery_task_id=task.id)
        )
    return BrowserUseTaskCreated(
        workflow_id=workflow_id,
        status=WorkflowStatus.PENDING,
        template_id=template_id,
    )


async def execute_browser_use_workflow(
    workflow_id: UUID,
    template_id: str,
    target_url: str,
    custom_prompt: str | None,
) -> dict:
    settings = get_settings()
    template = BROWSER_USE_TEMPLATES[template_id]
    prompt = custom_prompt or template.prompt
    client = BrowserUseCloudClient(settings.browser_use_api_key)
    await _update_workflow(workflow_id, status=WorkflowStatus.RUNNING, started=True)
    task = await client.create_task(
        task=f"{prompt}\nURL cible: {target_url}",
        metadata={"workflow_id": str(workflow_id), "template": template_id},
        allowed_domains=template.allowed_domains,
    )
    provider_task_id = task.get("id") or task.get("taskId")
    checkpoint = {
        "template_id": template_id,
        "provider_task_id": provider_task_id,
        "session_id": task.get("sessionId"),
    }
    await _update_workflow(workflow_id, checkpoint=checkpoint)

    elapsed = 0
    while elapsed < settings.browser_use_task_timeout_seconds:
        status = await client.get_task_status(provider_task_id)
        checkpoint.update({
            "provider_status": status.get("status"),
            "cost": status.get("cost"),
            "output": status.get("output"),
        })
        await _update_workflow(workflow_id, checkpoint=checkpoint)
        cost = status.get("cost")
        if isinstance(cost, (int, float)) and cost > settings.browser_use_task_cost_limit:
            await client.stop_task(provider_task_id)
            raise RuntimeError("Browser Use task cost limit exceeded")
        if status.get("status") in {"finished", "stopped"}:
            break
        await asyncio.sleep(settings.browser_use_poll_interval_seconds)
        elapsed += settings.browser_use_poll_interval_seconds
    else:
        await client.stop_task(provider_task_id)
        raise TimeoutError("Browser Use task timed out")

    detail = await client.get_task(provider_task_id)
    checkpoint.update(_safe_task_detail(detail))
    final_status = (
        WorkflowStatus.COMPLETED
        if detail.get("status") == "finished" and detail.get("isSuccess") is not False
        else WorkflowStatus.CANCELLED
    )
    await _update_workflow(
        workflow_id, status=final_status, checkpoint=checkpoint, finished=True
    )
    return checkpoint


async def list_browser_use_workflows(limit: int = 50) -> list[BrowserUseTaskView]:
    async with get_db() as db:
        rows = (
            await db.scalars(
                select(WorkflowRun)
                .where(WorkflowRun.workflow_type == "browser_use.task")
                .order_by(WorkflowRun.created_at.desc())
                .limit(limit)
            )
        ).all()
    return [_task_view(row) for row in rows]


async def stop_browser_use_workflow(workflow_id: UUID) -> BrowserUseTaskView:
    settings = get_settings()
    async with get_db() as db:
        workflow = await db.get(WorkflowRun, workflow_id)
    if workflow is None or workflow.workflow_type != "browser_use.task":
        raise ValueError("Browser Use workflow not found")
    provider_task_id = (workflow.checkpoint or {}).get("provider_task_id")
    if provider_task_id:
        await BrowserUseCloudClient(settings.browser_use_api_key).stop_task(provider_task_id)
    await _update_workflow(workflow_id, status=WorkflowStatus.CANCELLED, finished=True)
    async with get_db() as db:
        updated = await db.get(WorkflowRun, workflow_id)
    return _task_view(updated)


def _task_view(workflow: WorkflowRun) -> BrowserUseTaskView:
    checkpoint = workflow.checkpoint or {}
    return BrowserUseTaskView(
        workflow_id=workflow.id,
        status=workflow.status,
        template_id=checkpoint.get("template_id", "unknown"),
        target_url=workflow.target_id,
        provider_task_id=checkpoint.get("provider_task_id"),
        session_id=checkpoint.get("session_id"),
        cost=checkpoint.get("cost"),
        output=checkpoint.get("output"),
        output_files=checkpoint.get("output_files") or [],
        last_error=workflow.last_error,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
    )


def _safe_task_detail(detail: dict) -> dict:
    return {
        "provider_status": detail.get("status"),
        "output": detail.get("output"),
        "is_success": detail.get("isSuccess"),
        "output_files": detail.get("outputFiles") or [],
        "steps": detail.get("steps") or [],
    }


async def _update_workflow(
    workflow_id: UUID,
    *,
    status: WorkflowStatus | None = None,
    checkpoint: dict | None = None,
    started: bool = False,
    finished: bool = False,
) -> None:
    values = {}
    if status is not None:
        values["status"] = status
    if checkpoint is not None:
        values["checkpoint"] = checkpoint
    if started:
        values["started_at"] = datetime.now(UTC)
    if finished:
        values["finished_at"] = datetime.now(UTC)
    async with get_db() as db:
        await db.execute(
            update(WorkflowRun).where(WorkflowRun.id == workflow_id).values(**values)
        )
