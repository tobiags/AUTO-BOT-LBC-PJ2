from datetime import UTC, datetime, timedelta
from uuid import uuid4


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
