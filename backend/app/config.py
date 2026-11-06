from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://mindvault:mindvault@localhost:5432/mindvault"
    chunk_size: int = 800        # characters per chunk
    chunk_overlap: int = 120     # characters shared between neighbouring chunks
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384
    embedding_batch_size: int = 32
    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173"
    environment: str = "development"
    secret_key: str = "dev-secret-change-me"
    access_token_minutes: int = 60 * 24 * 7
    allow_registration: bool = True
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:1.5b"
    ollama_timeout: float = 180.0
    max_upload_mb: int = 10
    max_pdf_pages: int = 300
    rag_top_k: int = 4
    rag_min_score: float = 0.25
    embedding_threads: int = 2
    embed_retries: int = 2
    embed_retry_delay: float = 1.0


settings = Settings()
