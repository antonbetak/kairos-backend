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
        default="google_auth_service",
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

    google_client_id: str = Field(
        ...,
        validation_alias=AliasChoices("GOOGLE_CLIENT_ID", "google_client_id"),
    )
    google_client_secret: str = Field(
        ...,
        validation_alias=AliasChoices("GOOGLE_CLIENT_SECRET", "google_client_secret"),
    )
    google_client_id_ios: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GOOGLE_CLIENT_ID_IOS", "google_client_id_ios"),
    )
    google_client_id_android: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "GOOGLE_CLIENT_ID_ANDROID",
            "ANDROID_CLIENT",
            "android_client",
            "google_client_id_android",
        ),
    )
    auth_service_url: str = Field(
        default="http://auth_service:8000",
        validation_alias=AliasChoices("AUTH_SERVICE_URL", "auth_service_url"),
    )
    google_redirect_uri: str = Field(
        ...,
        validation_alias=AliasChoices("GOOGLE_REDIRECT_URI", "google_redirect_uri"),
    )
    google_redirect_uris: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GOOGLE_REDIRECT_URIS", "google_redirect_uris"),
    )
    google_auth_uri: str = Field(
        default="https://accounts.google.com/o/oauth2/v2/auth",
        validation_alias=AliasChoices("GOOGLE_AUTH_URI", "google_auth_uri"),
    )
    google_token_uri: str = Field(
        default="https://oauth2.googleapis.com/token",
        validation_alias=AliasChoices("GOOGLE_TOKEN_URI", "google_token_uri"),
    )
    google_userinfo_uri: str = Field(
        default="https://openidconnect.googleapis.com/v1/userinfo",
        validation_alias=AliasChoices("GOOGLE_USERINFO_URI", "google_userinfo_uri"),
    )
    google_scope: str = Field(
        default="openid email profile",
        validation_alias=AliasChoices("GOOGLE_SCOPE", "google_scope"),
    )
    state_ttl_seconds: int = Field(
        default=600,
        validation_alias=AliasChoices("STATE_TTL_SECONDS", "state_ttl_seconds"),
    )
    clock_skew_seconds: int = Field(
        default=10,
        validation_alias=AliasChoices("CLOCK_SKEW_SECONDS", "clock_skew_seconds"),
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

    def allowed_redirect_uris(self) -> list[str]:
        allowed = [self.google_redirect_uri]
        value = self.google_redirect_uris

        if value is None:
            return allowed

        value = str(value).strip()
        if not value:
            return allowed

        if value.startswith("["):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                parsed = None

            if isinstance(parsed, list):
                for item in parsed:
                    item_value = str(item).strip()
                    if item_value and item_value not in allowed:
                        allowed.append(item_value)
                return allowed

        parsed = [item.strip() for item in value.split(",") if item.strip()]
        for item in parsed:
            if item not in allowed:
                allowed.append(item)
        return allowed

    def allowed_google_client_ids(self) -> list[str]:
        allowed = [self.google_client_id]
        for item in (self.google_client_id_android, self.google_client_id_ios):
            if item and item not in allowed:
                allowed.append(item)
        return allowed


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
