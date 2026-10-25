"""
ESGPilot API — Configuration settings.
Loaded from environment variables / .env file.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application configuration."""

    # --- App ---
    app_name: str = "ESGPilot"
    environment: str = "development"
    log_level: str = "INFO"
    debug: bool = False

    # --- Database ---
    database_url: str = "postgresql+asyncpg://esgpilot:password@localhost:5432/esgpilot"
    database_url_sync: str = "postgresql://esgpilot:password@localhost:5432/esgpilot"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Qdrant ---
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str = ""

    # --- JWT / Auth ---
    jwt_secret_key: str = "change-this-to-a-real-secret-key"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 15

    # --- API Keys ---
    api_key_salt: str = "change-this-salt"

    # --- SLM Inference ---
    vllm_base_url: str = "http://localhost:8000/v1"
    model_name: str = "Qwen/Qwen2.5-7B-Instruct"
    ollama_base_url: str = "http://localhost:11434"

    # --- Embeddings ---
    embedding_model: str = "BAAI/bge-m3"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    embedding_dim: int = 1024

    # --- Retrieval ---
    retrieval_top_k: int = 30
    rerank_top_k: int = 6
    chunk_size: int = 512
    chunk_overlap: int = 50

    # --- Observability ---
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3000"

    # --- Rate Limits ---
    rate_limit_per_minute: int = 60
    nudge_cooldown_seconds: int = 300  # 5 min per section

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
