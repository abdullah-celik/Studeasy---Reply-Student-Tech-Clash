from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables / .env (see .env.example)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Which AI provider to use:
    # - "cloudflare": Workers AI, free daily allowance (10,000 Neurons/day), no training on data
    # - "mistral": needs a paid Mistral plan (new free accounts can't activate API keys)
    # - "openai": paid
    # The embedding size must match vector(N) in schema.sql: 1024 for Cloudflare (bge-m3)
    # and Mistral, 1536 for OpenAI.
    llm_provider: Literal["cloudflare", "mistral", "openai"] = "cloudflare"

    # Cloudflare Workers AI (dash.cloudflare.com -> AI -> Workers AI -> Use REST API)
    # Also accepts a few common spellings, so a typo in the dashboard doesn't take the app down.
    cloudflare_account_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "CLOUDFLARE_ACCOUNT_ID", "CLAUDFLARE_ACCOUNT_ID", "CLOUDFLARE_ACCOUNT", "CF_ACCOUNT_ID"
        ),
    )
    cloudflare_api_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "CLOUDFLARE_API_TOKEN",
            "CLAUDFLARE_API_TOKEN",
            "CLOUDFLARE_API_KEY",
            "CLAUDFLARE_API_KEY",
            "CLOUDFLARE_TOKEN",
            "CF_API_TOKEN",
        ),
    )
    cloudflare_chat_model: str = "@cf/meta/llama-4-scout-17b-16e-instruct"
    cloudflare_embedding_model: str = "@cf/baai/bge-m3"  # 1024 dimensions
    cloudflare_temperature: float = 0.3

    # Mistral (console.mistral.ai). Calls are throttled to stay under the plan's request rate.
    mistral_api_key: str | None = None
    mistral_chat_model: str = "mistral-small-latest"
    mistral_embedding_model: str = "mistral-embed"  # 1024 dimensions
    mistral_temperature: float = 0.3
    mistral_requests_per_second: float = 0.9

    # On startup, try the chat model (routing, a small quiz, a streamed answer) and the
    # embeddings once, and report the result in /api/health. Extra models (a JSON list,
    # e.g. ["@cf/zai-org/glm-4.7-flash"]) are tried too, which helps when choosing a model.
    ai_self_test: bool = True
    ai_self_test_extra_models: list[str] = ["@cf/zai-org/glm-4.7-flash"]

    # OpenAI
    openai_api_key: str | None = None
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
    # Empty = the provider's size (Mistral 1024, OpenAI 1536).
    embedding_dimensions: int | None = None

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
        "openai_temperature",
        "openai_reasoning_effort",
        "openai_structured_reasoning_effort",
        "openai_api_key",
        "mistral_api_key",
        "embedding_dimensions",
        "cloudflare_account_id",
        "cloudflare_api_token",
        mode="before",
    )
    @classmethod
    def _empty_is_none(cls, v):
        return None if isinstance(v, str) and not v.strip() else v

    @model_validator(mode="after")
    def _provider_key_present(self):
        required = {
            "cloudflare": {
                "CLOUDFLARE_ACCOUNT_ID": self.cloudflare_account_id,
                "CLOUDFLARE_API_TOKEN": self.cloudflare_api_token,
            },
            "mistral": {"MISTRAL_API_KEY": self.mistral_api_key},
            "openai": {"OPENAI_API_KEY": self.openai_api_key},
        }[self.llm_provider]
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(
                f"LLM_PROVIDER is {self.llm_provider!r} but {', '.join(missing)} is not set"
            )
        return self

    @property
    def vector_size(self) -> int:
        if self.embedding_dimensions:
            return self.embedding_dimensions
        return 1536 if self.llm_provider == "openai" else 1024

    @property
    def chat_model_name(self) -> str:
        return {
            "cloudflare": self.cloudflare_chat_model,
            "mistral": self.mistral_chat_model,
            "openai": self.openai_chat_model,
        }[self.llm_provider]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
