import json
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	model_config = SettingsConfigDict(
		env_file=(".env",),
		env_file_encoding="utf-8",
		extra="ignore",
		case_sensitive=False,
	)

	app_name: str = "google_auth_service"
	app_env: str = "development"
	log_level: str = "INFO"
	host: str = "0.0.0.0"
	port: int = 8000

	cors_origins: str = ""

	google_client_id: str
	google_client_secret: str
	google_redirect_uri: str
	google_auth_uri: str = "https://accounts.google.com/o/oauth2/v2/auth"
	google_token_uri: str = "https://oauth2.googleapis.com/token"
	google_userinfo_uri: str = "https://openidconnect.googleapis.com/v1/userinfo"
	google_scope: str = "openid email profile"
	state_ttl_seconds: int = 600
	clock_skew_seconds: int = 10

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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
	return Settings()
