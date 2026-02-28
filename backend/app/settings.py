"""Application settings from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/retail_forecast"
    database_url_sync: str = "postgresql://postgres:postgres@localhost:5433/retail_forecast"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Security
    api_key_admin: str = "dev-admin-key-change-in-production"

    # LLM
    llm_provider_default: str = "openai"
    openai_api_key: str = ""
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"

    # RAG
    rag_enabled: bool = True
    vectorstore: str = "chroma"
    embeddings_provider: str = "openai"
    rag_collection_name: str = "retail_knowledge"

    # Application
    log_level: str = "INFO"
    debug: bool = False

    # Paths (default for local; Docker uses /app/artifacts)
    artifacts_path: str = "./artifacts"


settings = Settings()
