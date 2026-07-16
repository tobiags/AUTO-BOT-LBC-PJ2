from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    env: str = "development"
    secret_key: str = "change-me"
    control_tower_token: str = ""
    control_tower_admin_user: str = ""
    control_tower_admin_password: str = ""
    strict_startup_validation: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://autotransfert:password@localhost:5432/autotransfert_p2"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Apify multi-account integration
    apify_token_encryption_key: str = ""
    apify_reconcile_minutes: int = 5
    apify_import_page_size: int = 250
    apify_ai_fallback_enabled: bool = False

    # SMSTools
    smstools_api_key: str = ""
    smstools_webhook_secret: str = ""

    # iproxy.online
    iproxy_api_key: str = ""
    iproxy_connection_id: str = ""
    iproxy_proxy_id: str = ""

    # SmsApp.io
    smsapp_api_token: str = ""
    smsapp_max_price_usd: float = 1.0
    smsapp_otp_country: str = "france"
    smsapp_otp_countries: str = "france,gb,nl,es,si,cy,de,it,at,cz,pt,pl"

    # Mailgun
    mailgun_api_key: str = ""
    mailgun_domain: str = ""
    mailgun_webhook_signing_key: str = ""
    operational_domain: str = ""
    mailgun_api_base_url: str = "https://api.eu.mailgun.net"

    # Sentry
    sentry_dsn: str = ""

    # browser-use Cloud (Mode B fallback)
    browser_use_api_key: str = ""
    browser_use_task_cost_limit: float = 2.0
    browser_use_poll_interval_seconds: int = 5
    browser_use_task_timeout_seconds: int = 900

    # Experimental engines remain isolated and opt-in.
    camoufox_enabled: bool = False
    obscura_enabled: bool = False
    lab_service_url: str = "http://experimental_lab:8010"
    lab_api_token: str = ""

    # Patchright sessions — répertoire des profils persistants
    sessions_dir: str = "runtime/modules/patchright/sessions"
    patchright_channel: str = "chrome"
    patchright_headless: bool = True
    patchright_no_viewport: bool = True


    # Fenêtre horaire SMS (règle R01 — heure Paris)
    sms_hour_start: int = 8
    sms_hour_end: int = 20
    sms_stop_number: str = "XXXX"

    # Pool comptes LBC (règle — minimum à maintenir)
    lbc_accounts_min_active: int = 3

    # Admin health token (optionnel)
    admin_health_token: str = ""

    @model_validator(mode="after")
    def validate_startup_settings(self):
        if self.apify_reconcile_minutes < 1:
            raise ValueError("apify_reconcile_minutes must be positive")
        if not 1 <= self.apify_import_page_size <= 1000:
            raise ValueError("apify_import_page_size must be between 1 and 1000")

        unsafe_secret = self.secret_key in {"change-me", "change-me-in-production"}
        if self.is_production_like() and unsafe_secret:
            raise ValueError("secret_key must be changed in production-like environments")

        if self.strict_startup_validation:
            self._require_all_or_none(
                "SMSTools",
                self.smstools_api_key,
                self.smstools_webhook_secret,
            )
            self._require_all_or_none(
                "iproxy.online",
                self.iproxy_api_key,
                self.iproxy_connection_id,
                self.iproxy_proxy_id,
            )
            self._require_all_or_none(
                "Mailgun",
                self.mailgun_api_key,
                self.mailgun_domain,
                self.mailgun_webhook_signing_key,
                self.operational_domain,
            )
        return self

    @staticmethod
    def _require_all_or_none(service: str, *values: str) -> None:
        configured = [bool(value) for value in values]
        if any(configured) and not all(configured):
            raise ValueError(f"{service} configuration is incomplete")

    def is_production_like(self) -> bool:
        return self.env in ("production", "staging")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
