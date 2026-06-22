"""Endpoint debug temporaire — capture le payload brut de SMSTools."""
import logging
from fastapi import APIRouter, Request

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = logging.getLogger(__name__)


@router.post("/debug")
async def debug_webhook(request: Request):
    body_bytes = await request.body()
    headers = dict(request.headers)
    try:
        body_json = await request.json()
    except Exception:
        body_json = body_bytes.decode(errors="replace")

    log.warning("DEBUG WEBHOOK headers=%s body=%s", headers, body_json)
    return {"ok": True, "received": body_json}
