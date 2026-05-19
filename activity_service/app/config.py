from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    activity_db_user: str
    activity_db_password: str
    activity_db_host: str
    activity_db_port: int
    activity_db_name: str
    auth_service_url: str = "http://auth_service:8000"
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.activity_db_user}:{self.activity_db_password}"
            f"@{self.activity_db_host}:{self.activity_db_port}/{self.activity_db_name}"
        )


settings = Settings()
