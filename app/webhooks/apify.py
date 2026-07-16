from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException

from app.models import ApifyWebhookPayload
from app.services.apify_runs import accept_webhook

router = APIRouter(prefix="/webhooks/apify", tags=["apify-webhook"])


@router.post("/{account_id}", status_code=202)
async def receive_apify_webhook(
    account_id: UUID,
    payload: ApifyWebhookPayload,
    authorization: Annotated[str | None, Header()] = None,
):
    try:
        queued = await accept_webhook(account_id, payload, authorization)
    except (LookupError, PermissionError) as exc:
        raise HTTPException(status_code=401, detail="invalid_apify_webhook") from exc
    if queued:
        from app.tasks import import_apify_run_task

        import_apify_run_task.delay(str(account_id), str(payload.resource["id"]))
    return {"accepted": True}
