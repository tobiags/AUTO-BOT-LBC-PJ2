from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_reject_partial_smstools_config():
    with pytest.raises(ValidationError):
        Settings(
            env="development",
            secret_key="local-secret",
            strict_startup_validation=True,
            sessions_dir=str(Path.cwd()),
            smstools_api_key="token-only",
        )


def test_settings_require_production_secrets():
    with pytest.raises(ValidationError):
        Settings(
            env="production",
            sessions_dir=str(Path.cwd()),
            secret_key="change-me-in-production",
        )


def test_settings_accept_complete_development_config():
    settings = Settings(
        env="development",
        secret_key="dev-secret",
        sessions_dir=str(Path.cwd()),
        smstools_api_key="smstools-key",
        smstools_webhook_secret="smstools-hook",
        iproxy_api_key="iproxy-key",
        iproxy_proxy_id="proxy-id",
        mailgun_api_key="mailgun-key",
        mailgun_domain="mg.example.com",
        mailgun_webhook_signing_key="mailgun-signing",
        operational_domain="example.com",
    )
    assert settings.secret_key == "dev-secret"
