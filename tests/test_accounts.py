from datetime import UTC, datetime
from uuid import uuid4

from app.models import AccountOut, AccountStatus, DatadomeTrustLevel


def test_account_out_exposes_created_email_and_otp_phone() -> None:
    account = AccountOut.model_validate(
        {
            "id": uuid4(),
            "email": "contact.test@mail.ecovente.com",
            "phone_otp": "+33612345678",
            "status": AccountStatus.EN_CREATION,
            "datadome_trust_level": DatadomeTrustLevel.LOW,
            "score_sante": 0,
            "quota_actuel": 0,
            "erreurs_24h": 0,
            "date_creation": datetime.now(UTC),
        }
    )

    assert account.email == "contact.test@mail.ecovente.com"
    assert account.phone_otp == "+33612345678"
