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
		default="google_fit_service",
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
	google_token_uri: str = Field(
		default="https://oauth2.googleapis.com/token",
		validation_alias=AliasChoices("GOOGLE_TOKEN_URI", "google_token_uri"),
	)
	google_tokeninfo_uri: str = Field(
		default="https://oauth2.googleapis.com/tokeninfo",
		validation_alias=AliasChoices("GOOGLE_TOKENINFO_URI", "google_tokeninfo_uri"),
	)
	google_fit_api_base: str = Field(
		default="https://www.googleapis.com/fitness/v1/users/me",
		validation_alias=AliasChoices("GOOGLE_FIT_API_BASE", "google_fit_api_base"),
	)
	google_fit_scopes: str = Field(
		default=(
			"https://www.googleapis.com/auth/fitness.activity.write "
			"https://www.googleapis.com/auth/fitness.location.write "
			"https://www.googleapis.com/auth/fitness.body.write"
		),
		validation_alias=AliasChoices("GOOGLE_FIT_SCOPES", "google_fit_scopes"),
	)
	request_timeout_seconds: float = Field(
		default=20.0,
		validation_alias=AliasChoices("REQUEST_TIMEOUT_SECONDS", "request_timeout_seconds"),
	)
	fit_bucket_days: int = Field(
		default=1,
		validation_alias=AliasChoices("FIT_BUCKET_DAYS", "fit_bucket_days"),
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
					str(origin).strip()
					for origin in parsed
					if str(origin).strip()
				]
				return cleaned or default_origins

		parsed = [origin.strip() for origin in value.split(",") if origin.strip()]
		return parsed or default_origins

	def fit_scopes_list(self) -> list[str]:
		scopes = [scope.strip() for scope in self.google_fit_scopes.split() if scope.strip()]
		return scopes


@lru_cache(maxsize=1)
def get_settings() -> Settings:
	return Settings()
