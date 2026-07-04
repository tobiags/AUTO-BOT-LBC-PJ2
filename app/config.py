from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    env: Literal["development", "test", "staging", "production"] = "development"
    secret_key: str = "change-me"
    admin_health_token: str = ""
    strict_startup_validation: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://autotransfert:password@localhost:5432/autotransfert_p2"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # SMSTools
    smstools_api_key: str = ""
    smstools_webhook_secret: str = ""

    # iproxy.online
    iproxy_api_key: str = ""
    iproxy_proxy_id: str = ""

    # SmsApp.io
    smsapp_api_token: str = ""

    # Mailgun
    mailgun_api_key: str = ""
    mailgun_domain: str = ""
    mailgun_webhook_signing_key: str = ""
    operational_domain: str = ""

    # Sentry
    sentry_dsn: str = ""

    # browser-use Cloud (Mode B fallback)
    browser_use_api_key: str = ""

    # Patchright sessions - repertoire des profils persistants
    sessions_dir: str = "/tmp/lbc_sessions"
    patchright_channel: str = "chrome"
    patchright_headless: bool = True
    patchright_no_viewport: bool = True
    healthcheck_timeout_seconds: float = Field(5.0, gt=0.1, le=30.0)

    # Fenetre horaire SMS (regle R01 - heure Paris)
    sms_hour_start: int = 8
    sms_hour_end: int = 20
    sms_stop_number: str = "XXXX"

    # Pool comptes LBC (regle - minimum a maintenir)
    lbc_accounts_min_active: int = 3

    def is_production_like(self) -> bool:
        return self.env in {"staging", "production"}

    @staticmethod
    def _is_absolute_path(value: str) -> bool:
        return Path(value).is_absolute() or value.startswith("/")

    def strict_validation_enabled(self) -> bool:
        return self.strict_startup_validation or self.is_production_like()

    @model_validator(mode="after")
    def validate_runtime_settings(self) -> "Settings":
        if self.sms_hour_start >= self.sms_hour_end:
            raise ValueError("sms_hour_start must be lower than sms_hour_end")

        if not self._is_absolute_path(self.sessions_dir):
            raise ValueError("sessions_dir must be an absolute path")

        if self.strict_startup_validation:
            self._validate_partial_integrations()
            self._validate_production_requirements()
        return self

    def _validate_partial_integrations(self) -> None:
        integration_fields = {
            "SMSTools": {
                "smstools_api_key": self.smstools_api_key,
                "smstools_webhook_secret": self.smstools_webhook_secret,
            },
            "iProxy": {
                "iproxy_api_key": self.iproxy_api_key,
                "iproxy_proxy_id": self.iproxy_proxy_id,
            },
            "Mailgun": {
                "mailgun_api_key": self.mailgun_api_key,
                "mailgun_domain": self.mailgun_domain,
                "mailgun_webhook_signing_key": self.mailgun_webhook_signing_key,
                "operational_domain": self.operational_domain,
            },
        }

        errors: list[str] = []
        for label, fields in integration_fields.items():
            provided = [name for name, value in fields.items() if str(value).strip()]
            if provided and len(provided) != len(fields):
                missing = [name for name, value in fields.items() if not str(value).strip()]
                errors.append(
                    f"{label} is partially configured; missing: {', '.join(missing)}"
                )

        if errors:
            raise ValueError("; ".join(errors))

    def _validate_production_requirements(self) -> None:
        if not self.is_production_like():
            return

        if self.secret_key in {"change-me", "change-me-in-production"}:
            raise ValueError("secret_key must be overridden outside development/test")

        required_fields = {
            "smstools_api_key": self.smstools_api_key,
            "smstools_webhook_secret": self.smstools_webhook_secret,
            "iproxy_api_key": self.iproxy_api_key,
            "iproxy_proxy_id": self.iproxy_proxy_id,
            "smsapp_api_token": self.smsapp_api_token,
            "mailgun_api_key": self.mailgun_api_key,
            "mailgun_domain": self.mailgun_domain,
            "mailgun_webhook_signing_key": self.mailgun_webhook_signing_key,
            "operational_domain": self.operational_domain,
            "sentry_dsn": self.sentry_dsn,
        }
        missing = [name for name, value in required_fields.items() if not str(value).strip()]
        if missing:
            raise ValueError(
                "Missing required production settings: " + ", ".join(sorted(missing))
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
