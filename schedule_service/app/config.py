from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    schedule_db_user: str
    schedule_db_password: str
    schedule_db_host: str
    schedule_db_port: int
    schedule_db_name: str
    auth_service_url: str = "http://auth_service:8000"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.schedule_db_user}:{self.schedule_db_password}"
            f"@{self.schedule_db_host}:{self.schedule_db_port}/{self.schedule_db_name}"
        )


settings = Settings()
