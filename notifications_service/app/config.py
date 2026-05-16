from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    notifications_db_user: str
    notifications_db_password: str
    notifications_db_host: str
    notifications_db_port: int
    notifications_db_name: str
    auth_service_url: str = "http://auth_service:8000"
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.notifications_db_user}:{self.notifications_db_password}"
            f"@{self.notifications_db_host}:{self.notifications_db_port}/{self.notifications_db_name}"
        )


settings = Settings()
