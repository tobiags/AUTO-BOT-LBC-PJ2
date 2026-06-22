"""
Webhook SMSTools → POST /webhooks/funds
Gère INSUFFICIENT_FUNDS et FUNDS_PURCHASED.
Met à jour service_balance en DB + push WS dashboard.
"""
import logging
from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import get_db
from app.models import SmsToolsFundsItem
from app.tables import ServiceBalance
from app.ws import ws_manager

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = logging.getLogger(__name__)

_LOW_THRESHOLD = 10.0


@router.post("/funds")
async def receive_funds(payload: list[SmsToolsFundsItem]):
    if not payload:
        return {"ok": True}

    item = payload[0]
    wtype = item.webhook_type
    funds = item.funds

    try:
        balance = float(funds.get("item_amount", 0))
    except (TypeError, ValueError):
        balance = None

    is_low = wtype == "insufficient_funds" or (balance is not None and balance < _LOW_THRESHOLD)
    now = datetime.now(UTC)

    async with get_db() as db:
        await db.execute(
            pg_insert(ServiceBalance)
            .values(
                service="smstools",
                label="SMSTools SMS",
                balance=balance,
                currency="EUR",
                is_low=is_low,
                low_threshold=_LOW_THRESHOLD,
                last_updated=now,
            )
            .on_conflict_do_update(
                index_elements=["service"],
                set_={
                    "balance": balance,
                    "is_low": is_low,
                    "last_updated": now,
                },
            )
        )
        await db.commit()

    log.warning("SMSTools fonds: type=%s balance=%s is_low=%s", wtype, balance, is_low)

    # Push WS pour mise à jour dashboard en temps réel
    await ws_manager.broadcast({
        "event": "balance_update",
        "service": "smstools",
        "balance": balance,
        "is_low": is_low,
    })

    return {"ok": True, "is_low": is_low}
