from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables / .env (see .env.example)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # OpenAI
    openai_api_key: str
    # GPT-6 Luna: OpenAI's budget model, text + image input (developers.openai.com/api/docs/models/gpt-6-luna)
    openai_chat_model: str = "gpt-6-luna"
    # Only sent when set; reasoning models may reject it.
    openai_temperature: float | None = None
    # Reasoning effort for free-text answers (tutor). Empty = don't send (for non-reasoning models).
    openai_reasoning_effort: str | None = "low"
    # Reasoning effort for structured calls (quiz, flashcards, reels, plans, routing, grading).
    # LangChain sends these tool calls through OpenAI's Responses API for GPT-6 models;
    # "none" keeps them fast and cheap. Empty = don't send.
    openai_structured_reasoning_effort: str | None = "none"
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
    # Optional regex for extra origins, e.g. Cloudflare Pages preview URLs:
    # https://([a-z0-9-]+\.)?studeasy\.pages\.dev
    cors_origin_regex: str | None = None
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


    @field_validator(
        "openai_temperature", "openai_reasoning_effort", "openai_structured_reasoning_effort",
        mode="before",
    )
    @classmethod
    def _empty_is_none(cls, v):
        return None if isinstance(v, str) and not v.strip() else v


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
