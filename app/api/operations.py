import secrets
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException

from app.config import get_settings
from app.models import (
    AccountCommandRequest,
    AccountCommandResponse,
    AccountCreateCommandRequest,
    AnalyzerCommandRequest,
    BrowserUseTaskCreated,
    BrowserUseTaskRequest,
    BrowserUseTaskView,
    CampaignCommandRequest,
    CampaignCommandResponse,
    CampaignCreateCommand,
    CampaignOut,
    ConnectorCommandRequest,
    ConnectorCommandResponse,
    InboxSyncRequest,
    LabRunRequest,
    LabRunView,
    LbcMessageView,
    WorkflowCommandRequest,
    WorkflowRunView,
)
from app.services.account_control import (
    create_account_command,
    execute_account_command,
    remove_quarantined_account,
)
from app.services.analyzer_control import queue_listing_analysis
from app.services.browser_use_workflows import (
    create_browser_use_workflow,
    list_browser_use_workflows,
    stop_browser_use_workflow,
)
from app.services.campaign_control import create_controlled_campaign, execute_campaign_command
from app.services.experimental_lab import cancel_lab_run, create_lab_run, list_lab_runs
from app.services.lbc_messaging import list_lbc_messages, queue_inbox_sync
from app.services.operations import execute_connector_command
from app.services.workflow_control import command_workflow, list_workflows

router = APIRouter(prefix="/api/v1/operations", tags=["operations"])


@router.post("/analyzer/listings/{listing_id}", response_model=WorkflowRunView)
async def analyze_listing_command(
    listing_id: UUID,
    command: AnalyzerCommandRequest,
    x_control_tower_token: Annotated[str | None, Header()] = None,
    x_operator_role: Annotated[str, Header()] = "operator",
    x_operator_id: Annotated[str, Header()] = "dashboard",
):
    role = _authorize(x_control_tower_token, x_operator_role)
    try:
        return await queue_listing_analysis(
            listing_id=listing_id,
            idempotency_key=command.idempotency_key,
            actor=x_operator_id[:100],
            role=role,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"code": "LISTING_NOT_FOUND"}) from exc


def _authorize(
    token: str | None,
    role: str,
    minimum: Literal["viewer", "operator", "admin"] = "operator",
) -> Literal["viewer", "operator", "admin"]:
    expected = get_settings().control_tower_token
    if not expected:
        raise HTTPException(status_code=503, detail={"code": "CONTROL_TOWER_NOT_CONFIGURED"})
    if token is None or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED"})
    if role not in {"viewer", "operator", "admin"}:
        raise HTTPException(status_code=403, detail={"code": "INVALID_ROLE"})
    rank = {"viewer": 0, "operator": 1, "admin": 2}
    if rank[role] < rank[minimum]:
        raise HTTPException(status_code=403, detail={"code": "INSUFFICIENT_ROLE"})
    return role


@router.post("/connectors/{connector}/commands", response_model=ConnectorCommandResponse)
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
    if connector not in {
        "database",
        "redis",
        "celery",
        "iproxy",
        "smstools",
        "smsapp",
        "mailgun",
        "browser_use",
        "sentry",
        "camoufox",
        "obscura",
    }:
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
    _authorize(x_control_tower_token, x_operator_role, "viewer")
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


@router.post("/browser-use/tasks/{workflow_id}/stop", response_model=BrowserUseTaskView)
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


@router.post("/campaigns/{campaign_id}/commands", response_model=CampaignCommandResponse)
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


@router.post("/campaigns", response_model=CampaignOut, status_code=201)
async def create_campaign_command(
    command: CampaignCreateCommand,
    x_control_tower_token: Annotated[str | None, Header()] = None,
    x_operator_role: Annotated[str, Header()] = "operator",
    x_operator_id: Annotated[str, Header()] = "dashboard",
):
    role = _authorize(x_control_tower_token, x_operator_role)
    return await create_controlled_campaign(
        campaign_type=command.type,
        message_template=command.message_template,
        quota_per_sim=command.quota_per_sim,
        search_criteria=command.search_criteria,
        idempotency_key=command.idempotency_key,
        actor=x_operator_id[:100],
        role=role,
    )


@router.get("/lab/runs", response_model=list[LabRunView])
async def lab_runs(
    x_control_tower_token: Annotated[str | None, Header()] = None,
    x_operator_role: Annotated[str, Header()] = "operator",
):
    _authorize(x_control_tower_token, x_operator_role, "viewer")
    return await list_lab_runs()


@router.post("/lab/runs", response_model=LabRunView)
async def start_lab_run(
    request: LabRunRequest,
    x_control_tower_token: Annotated[str | None, Header()] = None,
    x_operator_role: Annotated[str, Header()] = "operator",
    x_operator_id: Annotated[str, Header()] = "dashboard",
):
    role = _authorize(x_control_tower_token, x_operator_role)
    if role != "admin":
        raise HTTPException(status_code=403, detail={"code": "ADMIN_REQUIRED"})
    try:
        return await create_lab_run(
            engine=request.engine,
            target_url=str(request.target_url),
            idempotency_key=request.idempotency_key,
            actor=x_operator_id[:100],
            role=role,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "LAB_RUN_REJECTED", "message": str(exc)}
        ) from exc


@router.post("/lab/runs/{workflow_id}/stop", response_model=LabRunView)
async def stop_lab_run(
    workflow_id: UUID,
    x_control_tower_token: Annotated[str | None, Header()] = None,
    x_operator_role: Annotated[str, Header()] = "operator",
):
    _authorize(x_control_tower_token, x_operator_role, "admin")
    try:
        return await cancel_lab_run(workflow_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"code": "LAB_RUN_NOT_FOUND"}) from exc


@router.get("/messaging", response_model=list[LbcMessageView])
async def messaging_history(
    x_control_tower_token: Annotated[str | None, Header()] = None,
    x_operator_role: Annotated[str, Header()] = "operator",
):
    _authorize(x_control_tower_token, x_operator_role, "viewer")
    return await list_lbc_messages()


@router.post("/messaging/sync")
async def synchronize_messaging(
    request: InboxSyncRequest,
    x_control_tower_token: Annotated[str | None, Header()] = None,
    x_operator_role: Annotated[str, Header()] = "operator",
    x_operator_id: Annotated[str, Header()] = "dashboard",
):
    role = _authorize(x_control_tower_token, x_operator_role)
    workflow_id = await queue_inbox_sync(
        idempotency_key=request.idempotency_key,
        actor=x_operator_id[:100],
        role=role,
    )
    return {"workflow_id": workflow_id, "status": "queued"}


@router.post("/accounts/commands", response_model=AccountCommandResponse)
async def create_account_operation(
    command: AccountCreateCommandRequest,
    x_control_tower_token: Annotated[str | None, Header()] = None,
    x_operator_role: Annotated[str, Header()] = "operator",
    x_operator_id: Annotated[str, Header()] = "dashboard",
):
    role = _authorize(x_control_tower_token, x_operator_role)
    if role != "admin":
        raise HTTPException(status_code=403, detail={"code": "ADMIN_REQUIRED"})
    return await create_account_command(
        mode=command.mode,
        idempotency_key=command.idempotency_key,
        actor=x_operator_id[:100],
        role=role,
    )


@router.post("/accounts/{account_id}/commands", response_model=AccountCommandResponse)
async def account_operation(
    account_id: UUID,
    command: AccountCommandRequest,
    x_control_tower_token: Annotated[str | None, Header()] = None,
    x_operator_role: Annotated[str, Header()] = "operator",
    x_operator_id: Annotated[str, Header()] = "dashboard",
):
    role = _authorize(x_control_tower_token, x_operator_role)
    try:
        return await execute_account_command(
            account_id=account_id,
            action=command.action,
            idempotency_key=command.idempotency_key,
            actor=x_operator_id[:100],
            role=role,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"code": "ACCOUNT_NOT_FOUND"}) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "INVALID_ACCOUNT_COMMAND", "message": str(exc)},
        ) from exc


@router.delete("/accounts/{account_id}", response_model=AccountCommandResponse)
async def delete_quarantined_account(
    account_id: UUID,
    x_control_tower_token: Annotated[str | None, Header()] = None,
    x_operator_role: Annotated[str, Header()] = "operator",
    x_operator_id: Annotated[str, Header()] = "dashboard",
):
    role = _authorize(x_control_tower_token, x_operator_role)
    if role != "admin":
        raise HTTPException(status_code=403, detail={"code": "ADMIN_REQUIRED"})
    try:
        return await remove_quarantined_account(
            account_id=account_id,
            idempotency_key=f"delete-{account_id}-{secrets.token_urlsafe(12)}",
            actor=x_operator_id[:100],
            role=role,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"code": "ACCOUNT_NOT_FOUND"}) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "INVALID_ACCOUNT_DELETE", "message": str(exc)},
        ) from exc


@router.get("/workflows", response_model=list[WorkflowRunView])
async def workflow_history(
    x_control_tower_token: Annotated[str | None, Header()] = None,
    x_operator_role: Annotated[str, Header()] = "operator",
):
    _authorize(x_control_tower_token, x_operator_role, "viewer")
    return await list_workflows()


@router.post("/workflows/{workflow_id}/commands", response_model=WorkflowRunView)
async def workflow_operation(
    workflow_id: UUID,
    command: WorkflowCommandRequest,
    x_control_tower_token: Annotated[str | None, Header()] = None,
    x_operator_role: Annotated[str, Header()] = "operator",
    x_operator_id: Annotated[str, Header()] = "dashboard",
):
    role = _authorize(x_control_tower_token, x_operator_role)
    try:
        return await command_workflow(
            workflow_id=workflow_id,
            action=command.action,
            idempotency_key=command.idempotency_key,
            actor=x_operator_id[:100],
            role=role,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"code": "WORKFLOW_NOT_FOUND"}) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "INVALID_WORKFLOW_COMMAND", "message": str(exc)},
        ) from exc
