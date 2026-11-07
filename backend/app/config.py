from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables / .env (see .env.example)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # OpenAI
    openai_api_key: str
    openai_chat_model: str = "gpt-4o-mini"
    openai_temperature: float | None = 0.3
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Supabase
    supabase_url: str
    # Newer dashboards call it the "secret key" (sb_secret_...); accept common names.
    supabase_service_role_key: str = Field(
        validation_alias=AliasChoices(
            "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_KEY"
        )
    )

    # App
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    max_upload_mb: int = 25
    chunk_size: int = 1000
    chunk_overlap: int = 150
    retrieval_k: int = 6
    verify_answers: bool = True
    chat_history_limit: int = 10

    # Reels (short swipeable study cards). Server-wide switch; students also opt in.
    enable_reels: bool = True
    reels_page_size: int = 6
    reels_break_every: int = 15  # insert a "take a break" card after this many reels
    reels_session_minutes: int = 30  # views within this window count as one session


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
