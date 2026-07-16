from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException

from app.models import EmailIdentityBatchRequest, EmailIdentityCommandRequest, EmailIdentityOut
from app.services.email_identities import command_identity, generate_batch, list_identities

router = APIRouter(prefix="/api/v1/email-identities", tags=["email-identities"])


def _admin(role: str) -> None:
    if role != "admin":
        raise HTTPException(403, detail={"code": "ADMIN_REQUIRED"})


@router.get("", response_model=list[EmailIdentityOut])
async def list_email_identities():
    return [EmailIdentityOut.model_validate(row) for row in await list_identities()]


@router.post("/generate", response_model=list[EmailIdentityOut])
async def generate_email_identities(request: EmailIdentityBatchRequest, x_operator_role: Annotated[str, Header()] = "operator"):
    _admin(x_operator_role)
    try:
        return [EmailIdentityOut.model_validate(row) for row in await generate_batch(request.count)]
    except ValueError as exc:
        raise HTTPException(503, detail={"code": str(exc)}) from exc


@router.post("/{identity_id}/commands", response_model=EmailIdentityOut)
async def email_identity_command(identity_id: UUID, request: EmailIdentityCommandRequest, x_operator_role: Annotated[str, Header()] = "operator", x_operator_id: Annotated[str, Header()] = "dashboard"):
    _admin(x_operator_role)
    try:
        return EmailIdentityOut.model_validate(await command_identity(identity_id, request.action, x_operator_id[:120]))
    except LookupError as exc:
        raise HTTPException(404, detail={"code": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(409, detail={"code": str(exc)}) from exc
