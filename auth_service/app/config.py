from pydantic_settings import BaseSettings
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    auth_db_host: str
    auth_db_port: int
    auth_db_user: str
    auth_db_password: str
    auth_db_name: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    @property
    def database_url(self) -> URL:
        return URL.create(
            drivername="postgresql+psycopg2",
            username=self.auth_db_user,
            password=self.auth_db_password,
            host=self.auth_db_host,
            port=self.auth_db_port,
            database=self.auth_db_name,
        )


settings = Settings()
