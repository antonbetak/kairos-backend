from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    task_db_host: str
    task_db_port: int
    task_db_user: str
    task_db_password: str
    task_db_name: str
    auth_service_url: str = "http://auth_service:8000"
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.task_db_user}:{self.task_db_password}"
            f"@{self.task_db_host}:{self.task_db_port}/{self.task_db_name}"
        )


settings = Settings()
