from app.services.email_identities import build_identity
from app.tables import EmailIdentity


def test_build_identity_creates_a_named_address_for_operational_domain():
    identity = build_identity("mail.ecovente.com")

    assert identity.first_name
    assert identity.last_name
    assert identity.email.endswith("@mail.ecovente.com")
    assert identity.first_name.lower() in identity.email
    assert identity.last_name.lower() in identity.email


def test_identity_batch_only_allows_dashboard_sizes():
    from app.models import EmailIdentityBatchRequest

    assert EmailIdentityBatchRequest(count=10).count == 10


def test_email_identity_status_persists_enum_values():
    assert EmailIdentity.__table__.c.status.type.enums == [
        "available",
        "reserved",
        "used",
        "disabled",
    ]
