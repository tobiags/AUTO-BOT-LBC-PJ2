from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update

from app import boundaries
from app.db import get_db
from app.models import ConnectorCommandResponse, WorkflowStatus
from app.services.connector_monitor import probe_iproxy, probe_smstools
from app.tables import AuditEvent, WorkflowRun


async def execute_connector_command(
    *, connector: str, action: str, idempotency_key: str, actor: str, role: str
) -> ConnectorCommandResponse:
    workflow_type = f"connector.{connector}.{action}"
    async with get_db() as db:
        existing = await db.scalar(
            select(WorkflowRun).where(WorkflowRun.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return _response_from_workflow(existing, connector, action)

        workflow = WorkflowRun(
            idempotency_key=idempotency_key,
            workflow_type=workflow_type,
            target_type="connector",
            target_id=connector,
            status=WorkflowStatus.RUNNING,
            initiated_by=actor,
            started_at=datetime.now(UTC),
        )
        db.add(workflow)
        await db.flush()
        db.add(AuditEvent(
            actor=actor,
            role=role,
            action=workflow_type,
            target_type="connector",
            target_id=connector,
            idempotency_key=idempotency_key,
            input_summary={"action": action},
            result_status="running",
            workflow_run_id=workflow.id,
        ))
        workflow_id = workflow.id

    try:
        detail = await _run_connector_action(connector, action)
    except Exception as exc:
        await _finish_command(
            workflow_id, WorkflowStatus.FAILED,
            {"error": type(exc).__name__}, str(exc)[:500],
        )
        raise

    await _finish_command(workflow_id, WorkflowStatus.COMPLETED, detail)
    return ConnectorCommandResponse(
        command_id=workflow_id,
        status="completed",
        connector=connector,
        action=action,
        detail=detail,
    )


async def _run_connector_action(connector: str, action: str) -> dict:
    if action == "probe":
        if connector == "iproxy":
            result = await probe_iproxy()
        elif connector == "smstools":
            result = await probe_smstools()
        else:
            raise ValueError(f"Unsupported connector: {connector}")
        return result.model_dump(mode="json")
    if connector == "iproxy" and action == "rotate_ip":
        return {"rotated": await boundaries.rotate_4g_ip()}
    raise ValueError(f"Unsupported command: {connector}.{action}")


async def _finish_command(
    workflow_id: UUID,
    status: WorkflowStatus,
    detail: dict,
    error: str | None = None,
) -> None:
    async with get_db() as db:
        await db.execute(
            update(WorkflowRun).where(WorkflowRun.id == workflow_id).values(
                status=status,
                checkpoint=detail,
                last_error=error,
                finished_at=datetime.now(UTC),
            )
        )
        await db.execute(
            update(AuditEvent)
            .where(AuditEvent.workflow_run_id == workflow_id)
            .values(result_status=status.value.lower())
        )


def _response_from_workflow(
    workflow: WorkflowRun, connector: str, action: str
) -> ConnectorCommandResponse:
    return ConnectorCommandResponse(
        command_id=workflow.id,
        status=workflow.status.value.lower(),
        connector=connector,
        action=action,
        detail=workflow.checkpoint or {},
    )
