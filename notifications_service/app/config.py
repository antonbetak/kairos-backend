from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    notifications_db_user: str
    notifications_db_password: str
    notifications_db_host: str
    notifications_db_port: int
    notifications_db_name: str

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.notifications_db_user}:{self.notifications_db_password}"
            f"@{self.notifications_db_host}:{self.notifications_db_port}/{self.notifications_db_name}"
        )


settings = Settings()
