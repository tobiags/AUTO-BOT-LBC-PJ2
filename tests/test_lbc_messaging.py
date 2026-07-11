def test_extract_french_phone_numbers_normalizes_e164():
    from app.services.lbc_messaging import extract_phone_numbers

    assert extract_phone_numbers("Appelez-moi au 06 12 34 56 78 demain") == [
        "+33612345678"
    ]


def test_message_key_is_stable_across_retries():
    from app.services.lbc_messaging import outbound_message_key

    first = outbound_message_key("campaign-1", "listing-1")
    second = outbound_message_key("campaign-1", "listing-1")

    assert first == second
    assert first.startswith("outbound:")
