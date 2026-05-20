from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LangChain
    langchain_api_key: str = ""
    langchain_project: str = "kairos-agent-service"
    langchain_tracing_v2: str = "true"

    # Gemini
    gemini_api_key: str
    gemini_model: str = "gemini-1.5-flash"

    # ChromaDB
    chroma_host: str = "chromadb"
    chroma_port: int = 8000
    chroma_collection: str = "kairos_user_patterns"

    # Embeddings
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # RabbitMQ
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"

    # URLs internas
    task_service_url: str = "http://task_service:8000"
    stats_service_url: str = "http://stats_service:8000"

    # App
    app_name: str = "kairos-agent-service"


settings = Settings()
