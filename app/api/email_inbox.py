from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query

from app.models import EmailMessageListItemOut, EmailMessageOut, EmailMessagePageOut
from app.services.email_inbox import delete_email_message, get_email_message, list_email_messages, mark_email_message_read

router = APIRouter(prefix="/api/v1/email-messages", tags=["email-inbox"])


@router.get("", response_model=EmailMessagePageOut)
async def list_messages(
    identity_id: UUID | None = None,
    query: str | None = Query(default=None, max_length=200),
    unread_only: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    rows, total = await list_email_messages(
        identity_id=identity_id, query=query, unread_only=unread_only, limit=limit, offset=offset
    )
    return EmailMessagePageOut(items=[EmailMessageListItemOut.model_validate(row) for row in rows], total=total)


@router.get("/{message_id}", response_model=EmailMessageOut)
async def get_message(message_id: UUID):
    message = await get_email_message(message_id)
    if message is None:
        raise HTTPException(404, detail={"code": "EMAIL_MESSAGE_NOT_FOUND"})
    return EmailMessageOut.model_validate(message)


@router.post("/{message_id}/read", response_model=EmailMessageOut)
async def mark_read(message_id: UUID):
    message = await mark_email_message_read(message_id)
    if message is None:
        raise HTTPException(404, detail={"code": "EMAIL_MESSAGE_NOT_FOUND"})
    return EmailMessageOut.model_validate(message)


@router.delete("/{message_id}", status_code=204)
async def delete_message(message_id: UUID, x_operator_role: Annotated[str, Header()] = "operator"):
    if x_operator_role != "admin":
        raise HTTPException(403, detail={"code": "ADMIN_REQUIRED"})
    if not await delete_email_message(message_id):
        raise HTTPException(404, detail={"code": "EMAIL_MESSAGE_NOT_FOUND"})
