"""Environment-backed settings. Secrets come from the process environment."""

from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Employee Management System"
    app_env: str = "local"
    app_debug: bool = False
    api_v1_prefix: str = "/api/v1"
    secret_key: str = ""
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    database_url: str = "postgresql+asyncpg://ems:ems@localhost:5432/ems"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"
    log_json: bool = True
    org_timezone: str = "UTC"
    attendance_start_time: str = "09:15"
    login_rate_limit: int = 10
    login_rate_window_seconds: int = 300
    default_currency: str = "USD"
    bootstrap_admin_email: str = ""
    bootstrap_admin_password: str = ""

    @field_validator("org_timezone")
    @classmethod
    def timezone_must_exist(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown timezone: {value}") from exc
        return value

    @field_validator("attendance_start_time")
    @classmethod
    def attendance_time_must_parse(cls, value: str) -> str:
        parts = value.split(":")
        if len(parts) != 2 or not all(part.isdigit() for part in parts):
            raise ValueError("ATTENDANCE_START_TIME must be HH:MM")
        hour, minute = int(parts[0]), int(parts[1])
        if hour > 23 or minute > 59:
            raise ValueError("ATTENDANCE_START_TIME must be HH:MM")
        return f"{hour:02d}:{minute:02d}"

    @field_validator("default_currency")
    @classmethod
    def currency_must_be_iso(cls, value: str) -> str:
        code = value.strip().upper()
        if len(code) != 3 or not code.isalpha():
            raise ValueError("DEFAULT_CURRENCY must be a 3-letter code")
        return code

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]

    def validate_runtime(self) -> None:
        """Refuse to boot with a missing or weak secret outside local development."""
        if not self.secret_key:
            raise RuntimeError("SECRET_KEY is required.")
        if self.app_env != "local" and len(self.secret_key) < 32:
            raise RuntimeError(
                "SECRET_KEY must be at least 32 characters when APP_ENV is not local."
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
