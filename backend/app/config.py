"""
Alpha Pro MENA CRM — Application Configuration
All settings sourced from environment variables. Fails fast if required vars missing.
"""
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
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

    # Database
    database_url: str
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

    # CORS
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    # Google Sheets
    google_service_account_email: str = ""
    google_service_account_private_key: str = ""
    google_service_account_project_id: str = ""

    @property
    def google_sheets_enabled(self) -> bool:
        return bool(self.google_service_account_email and self.google_service_account_private_key)

    # Background Jobs & Automation
    job_overdue_task_check_minutes: int = 5
    job_google_sheets_sync_minutes: int = 15
    job_recall_reminder_minutes: int = 30
    job_notification_cleanup_days: int = 30
    no_answer_retry_hours: int = 48

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Admin Bootstrap
    admin_email: str = "admin@alphapro.com"
    admin_password: str = "Admin123!"
    admin_first_name: str = "System"
    admin_last_name: str = "Administrator"


@lru_cache
def get_settings() -> Settings:
    return Settings()
