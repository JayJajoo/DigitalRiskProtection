"""Application settings loaded from environment / .env.

All fields are optional so the app boots in Phase 0 without credentials. Later phases
read the relevant values (OpenAI, Anthropic, Elasticsearch, Chroma) when their features
are wired up.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Look for a .env at the repo root when running locally; ignored if absent.
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM / embeddings
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    anthropic_api_key: str = ""
    claude_enrichment_model: str = "claude-sonnet-5"
    claude_threat_model: str = "claude-opus-4-8"

    # Data stores
    elasticsearch_url: str = "http://localhost:9200"
    chroma_persist_dir: str = "./data/chroma"

    # Reserved (unused in this build)
    zerofox_token: str = ""

    @property
    def openai_configured(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def anthropic_configured(self) -> bool:
        return bool(self.anthropic_api_key)


settings = Settings()
