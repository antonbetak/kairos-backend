from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Gemini
    gemini_api_key: str
    gemini_model: str = "gemini-1.5-flash"

    # ChromaDB
    chroma_host: str = "chromadb"
    chroma_port: int = 8000
    chroma_collection: str = "kairos_user_patterns"

    # RabbitMQ
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"

    # URLs de otros servicios
    task_service_url: str = "http://task-service:8000"
    stats_service_url: str = "http://stats-service:8000"

    # App
    app_name: str = "kairos-agent-service"

    class Config:
        env_file = ".env"


settings = Settings()