import secrets
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException

from app.config import get_settings
from app.models import (
    BrowserUseTaskCreated,
    BrowserUseTaskRequest,
    BrowserUseTaskView,
    CampaignCommandRequest,
    CampaignCommandResponse,
    ConnectorCommandRequest,
    ConnectorCommandResponse,
)
from app.services.browser_use_workflows import (
    create_browser_use_workflow,
    list_browser_use_workflows,
    stop_browser_use_workflow,
)
from app.services.campaign_control import execute_campaign_command
from app.services.operations import execute_connector_command

router = APIRouter(prefix="/api/v1/operations", tags=["operations"])


def _authorize(token: str | None, role: str) -> Literal["operator", "admin"]:
    expected = get_settings().control_tower_token
    if not expected:
        raise HTTPException(
            status_code=503, detail={"code": "CONTROL_TOWER_NOT_CONFIGURED"}
        )
    if token is None or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED"})
    if role not in {"operator", "admin"}:
        raise HTTPException(status_code=403, detail={"code": "INVALID_ROLE"})
    return role


@router.post(
    "/connectors/{connector}/commands", response_model=ConnectorCommandResponse
)
async def connector_command(
    connector: str,
    command: ConnectorCommandRequest,
    x_control_tower_token: Annotated[str | None, Header()] = None,
    x_operator_role: Annotated[str, Header()] = "operator",
    x_operator_id: Annotated[str, Header()] = "dashboard",
):
    role = _authorize(x_control_tower_token, x_operator_role)
    if command.action == "rotate_ip" and (role != "admin" or not command.confirmed):
        raise HTTPException(
            status_code=403,
            detail={"code": "ADMIN_CONFIRMATION_REQUIRED"},
        )
    if connector not in {"iproxy", "smstools"}:
        raise HTTPException(status_code=404, detail={"code": "CONNECTOR_NOT_FOUND"})
    try:
        return await execute_connector_command(
            connector=connector,
            action=command.action,
            idempotency_key=command.idempotency_key,
            actor=x_operator_id[:100],
            role=role,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "UNSUPPORTED_COMMAND", "message": str(exc)},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "CONNECTOR_COMMAND_FAILED", "message": str(exc)[:300]},
        ) from exc


@router.get("/browser-use/tasks", response_model=list[BrowserUseTaskView])
async def browser_use_tasks(
    x_control_tower_token: Annotated[str | None, Header()] = None,
    x_operator_role: Annotated[str, Header()] = "operator",
):
    _authorize(x_control_tower_token, x_operator_role)
    return await list_browser_use_workflows()


@router.post("/browser-use/tasks", response_model=BrowserUseTaskCreated)
async def create_browser_use_task(
    task: BrowserUseTaskRequest,
    x_control_tower_token: Annotated[str | None, Header()] = None,
    x_operator_role: Annotated[str, Header()] = "operator",
    x_operator_id: Annotated[str, Header()] = "dashboard",
):
    role = _authorize(x_control_tower_token, x_operator_role)
    try:
        return await create_browser_use_workflow(
            template_id=task.template_id,
            target_url=str(task.target_url),
            idempotency_key=task.idempotency_key,
            actor=x_operator_id[:100],
            role=role,
            custom_prompt=task.custom_prompt,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=403, detail={"code": "ADMIN_REQUIRED", "message": str(exc)}
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_BROWSER_USE_TASK", "message": str(exc)},
        ) from exc


@router.post(
    "/browser-use/tasks/{workflow_id}/stop", response_model=BrowserUseTaskView
)
async def stop_browser_use_task(
    workflow_id: UUID,
    x_control_tower_token: Annotated[str | None, Header()] = None,
    x_operator_role: Annotated[str, Header()] = "operator",
):
    _authorize(x_control_tower_token, x_operator_role)
    try:
        return await stop_browser_use_workflow(workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND"}) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "BROWSER_USE_STOP_FAILED", "message": str(exc)[:300]},
        ) from exc


@router.post(
    "/campaigns/{campaign_id}/commands", response_model=CampaignCommandResponse
)
async def campaign_command(
    campaign_id: UUID,
    command: CampaignCommandRequest,
    x_control_tower_token: Annotated[str | None, Header()] = None,
    x_operator_role: Annotated[str, Header()] = "operator",
    x_operator_id: Annotated[str, Header()] = "dashboard",
):
    role = _authorize(x_control_tower_token, x_operator_role)
    try:
        return await execute_campaign_command(
            campaign_id=campaign_id,
            action=command.action,
            idempotency_key=command.idempotency_key,
            actor=x_operator_id[:100],
            role=role,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"code": "CAMPAIGN_NOT_FOUND"}) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "INVALID_CAMPAIGN_TRANSITION", "message": str(exc)},
        ) from exc
