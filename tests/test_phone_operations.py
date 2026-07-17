from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.db import get_db
from app.models import ActivationOrder, PhoneActivationStatus
from app.services.phone_operations import (
    cancel_phone_activation,
    reconcile_phone_activations,
    refresh_phone_activation,
    reserve_phone_activation,
)


def test_phone_activation_out_exposes_provider_lifecycle() -> None:
    from app.models import PhoneActivationOrigin, PhoneActivationOut, PhoneActivationStatus
    from app.tables import PhoneActivation

    expires_at = datetime.now(UTC) + timedelta(minutes=10)
    activation = PhoneActivation(
        id=uuid4(),
        provider="smsapp",
        provider_order_id="order-123",
        phone_e164="+33612345678",
        country="france",
        service="leboncoin",
        cost=0.35,
        status=PhoneActivationStatus.WAITING,
        origin=PhoneActivationOrigin.MANUAL,
        expires_at=expires_at,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    output = PhoneActivationOut.model_validate(activation)

    assert output.provider_order_id == "order-123"
    assert output.phone_e164 == "+33612345678"
    assert output.status is PhoneActivationStatus.WAITING
    assert output.origin is PhoneActivationOrigin.MANUAL
    assert output.expires_at == expires_at


@pytest.mark.integration
@patch("app.boundaries.buy_number_with_fallback", new_callable=AsyncMock)
async def test_manual_reservation_is_persisted_immediately(buy_number) -> None:
    provider_order_id = f"order-{uuid4()}"
    buy_number.return_value = ActivationOrder(
        id=provider_order_id,
        phone="+33700000001",
        country="france",
        service="leboncoin",
        cost=0.28,
        expires=int((datetime.now(UTC) + timedelta(minutes=10)).timestamp()),
    )

    activation = await reserve_phone_activation()

    assert activation.provider_order_id == provider_order_id
    assert activation.status == PhoneActivationStatus.WAITING
    assert activation.origin == "manual"


@pytest.mark.integration
@patch("app.boundaries.get_sms_activation", new_callable=AsyncMock)
@patch("app.boundaries.buy_number_with_fallback", new_callable=AsyncMock)
async def test_refresh_persists_received_otp(buy_number, get_activation) -> None:
    provider_order_id = f"order-{uuid4()}"
    buy_number.return_value = ActivationOrder(
        id=provider_order_id,
        phone="+33700000002",
        country="france",
        service="leboncoin",
        cost=0.28,
        expires=int((datetime.now(UTC) + timedelta(minutes=10)).timestamp()),
    )
    get_activation.return_value = {
        "status": "RECEIVED",
        "sms": [{"text": "Votre code Leboncoin est 847291"}],
    }
    activation = await reserve_phone_activation()

    refreshed = await refresh_phone_activation(activation.id)

    assert refreshed.status == PhoneActivationStatus.RECEIVED
    assert refreshed.received_code == "847291"
    assert refreshed.received_sms == "Votre code Leboncoin est 847291"


@pytest.mark.integration
@patch("app.boundaries.cancel_number", new_callable=AsyncMock, return_value=True)
@patch("app.boundaries.buy_number_with_fallback", new_callable=AsyncMock)
async def test_cancel_updates_local_lifecycle(buy_number, cancel_number) -> None:
    provider_order_id = f"order-{uuid4()}"
    buy_number.return_value = ActivationOrder(
        id=provider_order_id,
        phone="+33700000003",
        country="france",
        service="leboncoin",
        cost=0.28,
        expires=int((datetime.now(UTC) + timedelta(minutes=10)).timestamp()),
    )
    activation = await reserve_phone_activation()

    cancelled = await cancel_phone_activation(activation.id)

    assert cancelled.status == PhoneActivationStatus.CANCELLED
    cancel_number.assert_awaited_once_with(provider_order_id)


@pytest.mark.integration
@patch("app.boundaries.get_sms_activation", new_callable=AsyncMock)
@patch("app.boundaries.buy_number_with_fallback", new_callable=AsyncMock)
async def test_reconcile_expires_stale_numbers_without_provider_poll(
    buy_number, get_activation
) -> None:
    provider_order_id = f"order-{uuid4()}"
    buy_number.return_value = ActivationOrder(
        id=provider_order_id,
        phone="+33700000004",
        country="france",
        service="leboncoin",
        cost=0.28,
        expires=int((datetime.now(UTC) + timedelta(minutes=10)).timestamp()),
    )
    activation = await reserve_phone_activation()
    async with get_db() as db:
        stored = await db.get(type(activation), activation.id)
        stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)

    result = await reconcile_phone_activations()

    assert result["expired"] >= 1
    get_activation.assert_not_awaited()
