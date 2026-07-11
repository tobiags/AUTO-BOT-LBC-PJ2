import secrets
from typing import Annotated, Literal

from fastapi import APIRouter, Header, HTTPException

from app.config import get_settings
from app.models import ConnectorCommandRequest, ConnectorCommandResponse
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
