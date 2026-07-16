import pytest
from cryptography.fernet import Fernet

from app.services.apify_secrets import ApifySecretCodec


def test_secret_codec_round_trip_and_masking():
    codec = ApifySecretCodec(Fernet.generate_key().decode(), "app-test-secret")
    encrypted = codec.encrypt("apify_api_secret")

    assert encrypted != b"apify_api_secret"
    assert codec.decrypt(encrypted) == "apify_api_secret"
    assert codec.mask("apify_api_secret") == "apif...cret"


def test_secret_codec_fingerprint_is_stable_without_exposing_token():
    codec = ApifySecretCodec(Fernet.generate_key().decode(), "app-test-secret")
    first = codec.fingerprint("apify_api_secret")
    second = codec.fingerprint("apify_api_secret")

    assert first == second
    assert "apify_api_secret" not in first


def test_secret_codec_rejects_missing_master_key():
    with pytest.raises(RuntimeError, match="APIFY_TOKEN_ENCRYPTION_KEY"):
        ApifySecretCodec("", "app-test-secret")
