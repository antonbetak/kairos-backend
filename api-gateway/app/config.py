import json
from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
        case_sensitive=False,
    )

    app_name: str = Field(
        default="api_gateway",
        validation_alias=AliasChoices("APP_NAME", "app_name"),
    )
    app_env: str = Field(
        default="development",
        validation_alias=AliasChoices("APP_ENV", "app_env"),
    )
    log_level: str = Field(
        default="INFO",
        validation_alias=AliasChoices("APP_LOG_LEVEL", "log_level"),
    )
    host: str = Field(
        default="0.0.0.0",
        validation_alias=AliasChoices("APP_HOST", "host"),
    )
    port: int = Field(
        default=8000,
        validation_alias=AliasChoices("APP_PORT", "port"),
    )

    cors_origins: str = Field(
        default="",
        validation_alias=AliasChoices("CORS_ORIGINS", "cors_origins"),
    )

    google_auth_url: str = Field(
        default="http://google_auth:8000",
        validation_alias=AliasChoices("GOOGLE_AUTH_URL", "google_auth_url"),
    )
    calendar_service_url: str = Field(
        default="http://calendar-service:8000",
        validation_alias=AliasChoices("CALENDAR_SERVICE_URL", "calendar_service_url"),
    )
    google_fit_url: str = Field(
        default="http://googlefit_service:8000",
        validation_alias=AliasChoices("GOOGLE_FIT_URL", "google_fit_url"),
    )
    stt_service_url: str = Field(
        default="http://stt_service:8000",
        validation_alias=AliasChoices("STT_SERVICE_URL", "stt_service_url"),
    )
    notifications_service_url: str = Field(
        default="http://notifications_service:8000",
        validation_alias=AliasChoices(
            "NOTIFICATIONS_SERVICE_URL", "notifications_service_url"
        ),
    )
    stats_service_url: str = Field(
        default="http://stats_service:8000",
        validation_alias=AliasChoices("STATS_SERVICE_URL", "stats_service_url"),
    )
    agent_service_url: str = Field(
        default="http://agent_service:8000",
        validation_alias=AliasChoices("AGENT_SERVICE_URL", "agent_service_url"),
    )
    auth_service_url: str = Field(
        default="http://auth_service:8000",
        validation_alias=AliasChoices("AUTH_SERVICE_URL", "auth_service_url"),
    )
    activity_service_url: str = Field(
        default="http://activity_service:8000",
        validation_alias=AliasChoices("ACTIVITY_SERVICE_URL", "activity_service_url"),
    )
    clerk_secret_key: str = Field(
        default="",
        validation_alias=AliasChoices("CLERK_SECRET_KEY", "clerk_secret_key"),
    )
    clerk_api_base: str = Field(
        default="https://api.clerk.com/v1",
        validation_alias=AliasChoices("CLERK_API_BASE", "clerk_api_base"),
    )
    clerk_jwks_url: str = Field(
        default="",
        validation_alias=AliasChoices("CLERK_JWKS_URL", "clerk_jwks_url"),
    )
    google_scope: str = Field(
        default="openid email profile",
        validation_alias=AliasChoices("GOOGLE_SCOPE", "google_scope"),
    )
    internal_service_token: str = Field(
        default="",
        validation_alias=AliasChoices("INTERNAL_SERVICE_TOKEN", "internal_service_token"),
    )
    schedule_service_url: str = Field(
        default="http://schedule_service:8000",
        validation_alias=AliasChoices("SCHEDULE_SERVICE_URL", "schedule_service_url"),
    )
    task_service_url: str = Field(
        default="http://task_service:8000",
        validation_alias=AliasChoices("TASK_SERVICE_URL", "task_service_url"),
    )

    request_timeout_seconds: float = Field(
        default=20.0,
        validation_alias=AliasChoices(
            "REQUEST_TIMEOUT_SECONDS", "request_timeout_seconds"
        ),
    )

    def cors_origins_list(self) -> list[str]:
        default_origins = [
            "http://localhost:3000",
            "http://localhost:8081",
            "http://localhost:19006",
        ]

        value = self.cors_origins
        if value is None:
            return default_origins

        value = str(value).strip()
        if not value:
            return default_origins

        if value.startswith("["):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                parsed = None

            if isinstance(parsed, list):
                cleaned = [
                    str(origin).strip() for origin in parsed if str(origin).strip()
                ]
                return cleaned or default_origins

        parsed = [origin.strip() for origin in value.split(",") if origin.strip()]
        return parsed or default_origins

    def google_required_scopes_list(self) -> list[str]:
        value = self.google_scope
        if value is None:
            return []

        return [scope.strip() for scope in str(value).split() if scope.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()