import csv
import io
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.models import (
    PhoneActivationCreate,
    PhoneActivationOut,
    PhoneActivationPageOut,
    PhoneOperationsSummaryOut,
    SmsMessageOut,
    SmsMessagePageOut,
)
from app.services.phone_operations import (
    cancel_phone_activation,
    list_phone_activations,
    list_sms_messages,
    phone_operations_summary,
    refresh_phone_activation,
    reserve_phone_activation,
)
from app.tables import SmsLog

router = APIRouter(prefix="/api/v1/phone-operations", tags=["phone-operations"])
settings = get_settings()


def _sms_out(row: SmsLog) -> SmsMessageOut:
    return SmsMessageOut(
        id=row.id,
        direction=row.direction,
        phone_e164=row.to_phone,
        sim_id=row.sim_id,
        body=row.body,
        status=str(row.status),
        project=row.project,
        cost_eur=row.cost_eur,
        campaign_id=row.campaign_id,
        contact_id=row.contact_id,
        listing_id=row.listing_id,
        sequence_step=row.sequence_step,
        variant_key=row.variant_key,
        classification=row.classification,
        occurred_at=row.received_at or row.sent_at,
    )


@router.get("/summary", response_model=PhoneOperationsSummaryOut)
async def get_summary():
    return PhoneOperationsSummaryOut(**await phone_operations_summary())


@router.get("/activations", response_model=PhoneActivationPageOut)
async def get_activations(
    status: str | None = Query(default=None, max_length=20),
    query: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    rows, total = await list_phone_activations(
        status=status, query=query, limit=limit, offset=offset
    )
    return PhoneActivationPageOut(
        items=[PhoneActivationOut.model_validate(row) for row in rows], total=total
    )


@router.post("/activations", response_model=PhoneActivationOut, status_code=201)
async def create_activation(payload: PhoneActivationCreate):
    if not settings.smsapp_api_token:
        raise HTTPException(503, detail={"code": "SMSAPP_NOT_CONFIGURED"})
    try:
        row = await reserve_phone_activation(country=payload.country, service=payload.service)
    except Exception as exc:
        raise HTTPException(502, detail={"code": "PHONE_RESERVATION_FAILED"}) from exc
    return PhoneActivationOut.model_validate(row)


@router.post("/activations/{activation_id}/refresh", response_model=PhoneActivationOut)
async def refresh_activation(activation_id: UUID):
    try:
        return PhoneActivationOut.model_validate(await refresh_phone_activation(activation_id))
    except LookupError as exc:
        raise HTTPException(404, detail={"code": "PHONE_ACTIVATION_NOT_FOUND"}) from exc


@router.post("/activations/{activation_id}/cancel", response_model=PhoneActivationOut)
async def cancel_activation(activation_id: UUID):
    try:
        return PhoneActivationOut.model_validate(await cancel_phone_activation(activation_id))
    except LookupError as exc:
        raise HTTPException(404, detail={"code": "PHONE_ACTIVATION_NOT_FOUND"}) from exc


@router.get("/messages", response_model=SmsMessagePageOut)
async def get_messages(
    direction: str | None = Query(default=None, pattern="^(inbound|outbound)$"),
    status: str | None = Query(default=None, max_length=30),
    query: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    rows, total = await list_sms_messages(
        direction=direction, status=status, query=query, limit=limit, offset=offset
    )
    return SmsMessagePageOut(items=[_sms_out(row) for row in rows], total=total)


@router.get("/messages.csv")
async def export_messages(
    direction: str | None = Query(default=None, pattern="^(inbound|outbound)$"),
    status: str | None = Query(default=None, max_length=30),
    query: str | None = Query(default=None, max_length=120),
):
    rows, _ = await list_sms_messages(
        direction=direction, status=status, query=query, limit=10_000, offset=0
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["date", "direction", "telephone", "sim", "statut", "message", "cout_eur"]
    )
    for row in rows:
        writer.writerow(
            [
                (row.received_at or row.sent_at).isoformat(),
                row.direction,
                row.to_phone,
                row.sim_id,
                str(row.status),
                row.body,
                row.cost_eur if row.cost_eur is not None else "",
            ]
        )
    headers = {"Content-Disposition": 'attachment; filename="sms-history.csv"'}
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers=headers)
