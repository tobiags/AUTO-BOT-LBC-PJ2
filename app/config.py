from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    env: str = "development"
    secret_key: str = "change-me"

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

    # Patchright sessions — répertoire des profils persistants
    sessions_dir: str = "/tmp/lbc_sessions"

    # Fenêtre horaire SMS (règle R01 — heure Paris)
    sms_hour_start: int = 8
    sms_hour_end: int = 20

    # Pool comptes LBC (règle — minimum à maintenir)
    lbc_accounts_min_active: int = 3


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
