from app.services.email_identities import build_identity


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
