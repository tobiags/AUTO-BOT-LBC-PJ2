"""Lifecycle management for short-lived OTP phone activations."""

import re
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app import boundaries
from app.db import get_db
from app.models import (
    ActivationOrder,
    PhoneActivationOrigin,
    PhoneActivationStatus,
)
from app.tables import PhoneActivation

ACTIVE_STATUSES = {
    PhoneActivationStatus.RESERVED.value,
    PhoneActivationStatus.WAITING.value,
}
TERMINAL_STATUSES = {
    PhoneActivationStatus.USED.value,
    PhoneActivationStatus.CANCELLED.value,
    PhoneActivationStatus.EXPIRED.value,
    PhoneActivationStatus.REFUNDED.value,
    PhoneActivationStatus.FAILED.value,
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _expiry(order: ActivationOrder) -> datetime:
    if order.expires > 0:
        return datetime.fromtimestamp(order.expires, UTC)
    return _utcnow() + timedelta(minutes=2)


def _sanitize_error(exc: Exception) -> str:
    message = str(exc)
    message = re.sub(r"(?i)bearer\s+[a-z0-9._~-]+", "Bearer [redacted]", message)
    return message[:500]


def _sms_text(payload: dict) -> str | None:
    sms = payload.get("sms")
    if isinstance(sms, list) and sms:
        first = sms[0]
        if isinstance(first, dict):
            return str(first.get("text") or "").strip() or None
        return str(first).strip() or None
    if isinstance(sms, dict):
        return str(sms.get("text") or "").strip() or None
    if isinstance(sms, str):
        return sms.strip() or None
    return None


def _otp_code(text: str | None) -> str | None:
    if not text:
        return None
    matches = re.findall(r"\b\d{4,8}\b", text)
    return matches[0] if matches else None


async def record_phone_activation(
    order: ActivationOrder,
    *,
    origin: PhoneActivationOrigin = PhoneActivationOrigin.AUTOMATIC,
    workflow_id: str | None = None,
    platform_account_id: uuid.UUID | None = None,
) -> PhoneActivation:
    async with get_db() as db:
        existing = (
            await db.execute(
                select(PhoneActivation).where(
                    PhoneActivation.provider_order_id == order.id
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            if platform_account_id is not None:
                existing.platform_account_id = platform_account_id
            if workflow_id is not None:
                existing.workflow_id = workflow_id
            return existing
        activation = PhoneActivation(
            provider="smsapp",
            provider_order_id=order.id,
            phone_e164=order.phone,
            country=order.country,
            service=order.service,
            cost=order.cost,
            status=PhoneActivationStatus.WAITING.value,
            origin=origin.value,
            platform_account_id=platform_account_id,
            workflow_id=workflow_id,
            expires_at=_expiry(order),
        )
        db.add(activation)
        await db.flush()
        return activation


async def reserve_phone_activation(
    *,
    country: str | None = None,
    service: str = "leboncoin",
    origin: PhoneActivationOrigin = PhoneActivationOrigin.MANUAL,
    workflow_id: str | None = None,
) -> PhoneActivation:
    order = (
        await boundaries.buy_number(country, service)
        if country
        else await boundaries.buy_number_with_fallback(service)
    )
    return await record_phone_activation(order, origin=origin, workflow_id=workflow_id)


async def refresh_phone_activation(activation_id: uuid.UUID) -> PhoneActivation:
    async with get_db() as db:
        activation = await db.get(PhoneActivation, activation_id)
        if activation is None:
            raise LookupError("phone_activation_not_found")
        if activation.status in TERMINAL_STATUSES or activation.status == PhoneActivationStatus.RECEIVED:
            return activation
        if activation.expires_at <= _utcnow():
            activation.status = PhoneActivationStatus.EXPIRED.value
            return activation
        try:
            payload = await boundaries.get_sms_activation(activation.provider_order_id)
        except Exception as exc:
            activation.last_error = _sanitize_error(exc)
            return activation
        provider_status = str(payload.get("status") or "").upper()
        text = _sms_text(payload)
        if provider_status == "RECEIVED" and text:
            activation.status = PhoneActivationStatus.RECEIVED.value
            activation.received_sms = text
            activation.received_code = _otp_code(text)
            activation.received_at = _utcnow()
            activation.last_error = None
        elif provider_status in {"CANCELLED", "CANCELED"}:
            activation.status = PhoneActivationStatus.CANCELLED.value
        elif provider_status in {"EXPIRED", "TIMEOUT"}:
            activation.status = PhoneActivationStatus.EXPIRED.value
        elif provider_status in {"REFUNDED"}:
            activation.status = PhoneActivationStatus.REFUNDED.value
        return activation


async def cancel_phone_activation(activation_id: uuid.UUID) -> PhoneActivation:
    async with get_db() as db:
        activation = await db.get(PhoneActivation, activation_id)
        if activation is None:
            raise LookupError("phone_activation_not_found")
        if activation.status in TERMINAL_STATUSES:
            return activation
        try:
            cancelled = await boundaries.cancel_number(activation.provider_order_id)
        except Exception as exc:
            activation.last_error = _sanitize_error(exc)
            return activation
        if cancelled:
            activation.status = PhoneActivationStatus.CANCELLED.value
            activation.last_error = None
        else:
            activation.last_error = "provider_cancellation_rejected"
        return activation


async def link_phone_activation(
    provider_order_id: str, platform_account_id: uuid.UUID
) -> PhoneActivation:
    async with get_db() as db:
        activation = (
            await db.execute(
                select(PhoneActivation).where(
                    PhoneActivation.provider_order_id == provider_order_id
                )
            )
        ).scalar_one_or_none()
        if activation is None:
            raise LookupError("phone_activation_not_found")
        activation.platform_account_id = platform_account_id
        return activation


async def mark_phone_activation_received(
    provider_order_id: str, code: str, sms_text: str | None = None
) -> None:
    async with get_db() as db:
        activation = (
            await db.execute(
                select(PhoneActivation).where(
                    PhoneActivation.provider_order_id == provider_order_id
                )
            )
        ).scalar_one_or_none()
        if activation is not None:
            activation.status = PhoneActivationStatus.RECEIVED.value
            activation.received_code = code
            activation.received_sms = sms_text or activation.received_sms
            activation.received_at = _utcnow()


async def mark_phone_activation_used(provider_order_id: str) -> None:
    async with get_db() as db:
        activation = (
            await db.execute(
                select(PhoneActivation).where(
                    PhoneActivation.provider_order_id == provider_order_id
                )
            )
        ).scalar_one_or_none()
        if activation is not None:
            activation.status = PhoneActivationStatus.USED.value
            activation.used_at = _utcnow()


async def reconcile_phone_activations(limit: int = 100) -> dict[str, int]:
    now = _utcnow()
    async with get_db() as db:
        activations = (
            await db.scalars(
                select(PhoneActivation)
                .where(PhoneActivation.status.in_(ACTIVE_STATUSES))
                .order_by(PhoneActivation.created_at.desc())
                .limit(limit)
            )
        ).all()
        refresh_ids: list[uuid.UUID] = []
        expired = 0
        for activation in activations:
            if activation.expires_at <= now:
                activation.status = PhoneActivationStatus.EXPIRED.value
                expired += 1
            else:
                refresh_ids.append(activation.id)
    received = 0
    for activation_id in refresh_ids:
        activation = await refresh_phone_activation(activation_id)
        if activation.status == PhoneActivationStatus.RECEIVED:
            received += 1
    return {"checked": len(activations), "expired": expired, "received": received}
