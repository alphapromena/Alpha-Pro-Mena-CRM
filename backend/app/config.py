"""
Alpha Pro MENA CRM — Application Configuration
All settings sourced from environment variables. Fails fast if required vars missing.

Database URL handling accepts what local .env files and hosted Postgres providers
(Vercel / Neon / Supabase) hand out and normalises it for the async SQLAlchemy engine.
"""
import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


def running_on_vercel() -> bool:
    return bool(os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"))


def normalize_database_url(url: str) -> Tuple[str, bool]:
    """
    Return (sqlalchemy_async_url, uses_external_pooler).

    - sqlite relative paths are anchored to the backend/ directory so the DB file
      does not depend on the current working directory.
    - postgres:// | postgresql:// | postgresql+psycopg2://  ->  postgresql+asyncpg://
    - ?sslmode=require (libpq)                              ->  ?ssl=require (asyncpg)
    - ?pgbouncer=true or a *pooler* host (Supabase/Neon)    ->  prepared statements disabled
    """
    url = url.strip()
    if url.startswith("sqlite"):
        prefix, _, path = url.partition(":///")
        if path and path != ":memory:" and not Path(path).is_absolute():
            path = (BACKEND_DIR / path).resolve().as_posix()
            return f"{prefix}:///{path}", False
        return url, False

    parts = urlsplit(url)
    scheme = parts.scheme
    if scheme in ("postgres", "postgresql", "postgresql+psycopg2", "postgresql+psycopg"):
        scheme = "postgresql+asyncpg"

    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    pooled = query.pop("pgbouncer", "").lower() == "true" or "pooler" in (parts.hostname or "")

    sslmode = query.pop("sslmode", None)
    if sslmode and sslmode != "disable" and "ssl" not in query:
        query["ssl"] = "require"
    # libpq-only parameters asyncpg does not understand
    for key in ("channel_binding", "options", "supa", "schema"):
        query.pop(key, None)
    if pooled:
        # SQLAlchemy's own prepared-statement cache must be off behind a transaction pooler
        query["prepared_statement_cache_size"] = "0"

    return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)), pooled


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(BACKEND_DIR / ".env"), ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: str = "development"
    app_secret_key: str
    app_debug: bool = False
    frontend_url: str = "http://localhost:5173"
    app_version: str = "1.0.0"
    app_name: str = "Alpha Pro MENA CRM"

    # Database: DATABASE_URL, or the POSTGRES_URL that Vercel storage integrations inject
    database_url: str = Field(
        validation_alias=AliasChoices("DATABASE_URL", "POSTGRES_URL", "POSTGRES_PRISMA_URL")
    )
    database_pooled: bool = False
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # JWT
    jwt_secret_key: str
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    jwt_algorithm: str = "HS256"

    # Rate Limiting
    rate_limit_login: str = "5/minute"
    rate_limit_default: str = "200/minute"

    # Company Email & Identity
    company_email_domain: str = "alphapromena.com"

    # Email & SMTP Service
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "noreply@alphapromena.com"
    smtp_use_tls: bool = True
    verification_token_expire_hours: int = 24
    password_reset_token_expire_hours: int = 2
    verification_resend_cooldown_seconds: int = 60

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_port)

    # CORS
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # Google Sheets
    google_service_account_email: str = ""
    google_service_account_private_key: str = ""
    google_service_account_project_id: str = ""

    @property
    def google_sheets_enabled(self) -> bool:
        return bool(self.google_service_account_email and self.google_service_account_private_key)

    # Background Jobs & Automation
    # ENABLE_SCHEDULER: run APScheduler inside the API process (long-running servers).
    # Leave unset to auto-detect: on locally / in Docker, off on Vercel where crons call /api/v1/jobs/*.
    enable_scheduler: Optional[bool] = None
    cron_secret: str = ""  # Bearer token Vercel Cron sends to /api/v1/jobs/* (set CRON_SECRET)
    job_overdue_task_check_minutes: int = 5
    job_google_sheets_sync_minutes: int = 15
    job_recall_reminder_minutes: int = 30
    job_notification_cleanup_days: int = 30
    no_answer_retry_hours: int = 48

    @property
    def is_serverless(self) -> bool:
        return running_on_vercel()

    @property
    def scheduler_enabled(self) -> bool:
        if self.enable_scheduler is not None:
            return self.enable_scheduler
        return not self.is_serverless

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Admin Bootstrap (seed script only)
    admin_email: str = "admin@alphapro.com"
    admin_password: str = ""
    admin_first_name: str = "System"
    admin_last_name: str = "Administrator"

    @model_validator(mode="after")
    def _finalize(self) -> "Settings":
        self.database_url, self.database_pooled = normalize_database_url(self.database_url)
        if self.app_env == "production":
            for name in ("app_secret_key", "jwt_secret_key"):
                if len(getattr(self, name)) < 32:
                    raise ValueError(f"{name.upper()} must be at least 32 characters in production.")
            if self.database_url.startswith("sqlite"):
                raise ValueError("SQLite is not supported in production. Set DATABASE_URL to PostgreSQL.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
