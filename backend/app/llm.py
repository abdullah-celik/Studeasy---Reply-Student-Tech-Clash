"""One place that builds the chat and embedding models.

LLM_PROVIDER picks the provider:
- cloudflare: Workers AI through its OpenAI-compatible endpoint (free daily allowance)
- mistral: Mistral API; calls share one throttle to stay under the plan's request rate
- openai: OpenAI (GPT-6 Luna)
"""

from functools import lru_cache
from typing import Any

import httpx
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.rate_limiters import InMemoryRateLimiter
from pydantic import BaseModel, Field

from app.config import get_settings


def cloudflare_base_url() -> str:
    account = get_settings().cloudflare_account_id
    return f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/v1"


@lru_cache
def _throttle() -> InMemoryRateLimiter:
    return InMemoryRateLimiter(
        requests_per_second=get_settings().mistral_requests_per_second,
        check_every_n_seconds=0.05,
        max_bucket_size=1,  # no bursts
    )


@lru_cache
def _cloudflare_chat(model: str) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    s = get_settings()
    return ChatOpenAI(
        model=model,
        api_key=s.cloudflare_api_token,
        base_url=cloudflare_base_url(),
        temperature=s.cloudflare_temperature,
        streaming=True,
        stream_usage=False,
        use_responses_api=False,
        max_retries=2,
    )


@lru_cache
def _mistral_chat() -> BaseChatModel:
    from langchain_mistralai import ChatMistralAI

    s = get_settings()
    return ChatMistralAI(
        model=s.mistral_chat_model,
        api_key=s.mistral_api_key,
        temperature=s.mistral_temperature,
        streaming=True,
        rate_limiter=_throttle(),
    )


@lru_cache
def _model(reasoning_effort: str | None) -> BaseChatModel:
    s = get_settings()
    # Reasoning effort is an OpenAI setting; the other providers use one instance.
    if s.llm_provider == "cloudflare":
        return _cloudflare_chat(s.cloudflare_chat_model)
    if s.llm_provider == "mistral":
        return _mistral_chat()

    from langchain_openai import ChatOpenAI

    kwargs = {}
    if s.openai_temperature is not None:
        kwargs["temperature"] = s.openai_temperature
    if reasoning_effort:
        kwargs["reasoning_effort"] = reasoning_effort
    return ChatOpenAI(
        model=s.openai_chat_model,
        api_key=s.openai_api_key,
        streaming=True,
        **kwargs,
    )


def chat_model(model: str | None = None) -> BaseChatModel:
    """Free-text answers (tutor). OpenAI: uses OPENAI_REASONING_EFFORT.

    `model` picks another Cloudflare model (used by the startup self-test).
    """
    if model and get_settings().llm_provider == "cloudflare":
        return _cloudflare_chat(model)
    return _model(get_settings().openai_reasoning_effort)


def structured(schema: type[BaseModel], model: str | None = None):
    """Chat model that returns a validated Pydantic object.

    function_calling is used instead of strict json_schema because strict mode
    rejects optional fields / defaults, which our schemas use. For GPT-6 models LangChain
    routes tool calls through the Responses API; effort comes from
    OPENAI_STRUCTURED_REASONING_EFFORT ("none" by default: fast and cheap).
    """
    if model and get_settings().llm_provider == "cloudflare":
        base = _cloudflare_chat(model)
    else:
        base = _model(get_settings().openai_structured_reasoning_effort)
    # Retries: the model returned something that failed validation, or the API was busy.
    return base.with_structured_output(schema, method="function_calling").with_retry(
        stop_after_attempt=3
    )


def _mistral_embeddings() -> Embeddings:
    from langchain_mistralai import MistralAIEmbeddings
    from langchain_mistralai.embeddings import DummyTokenizer

    class ThrottledMistralEmbeddings(MistralAIEmbeddings):
        """Sends batches one after another through the shared throttle."""

        tokenizer: Any = Field(default=None)  # also accept the character-based DummyTokenizer

        async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
            vectors: list[list[float]] = []
            for batch in self._get_batches(texts):
                await _throttle().aacquire()
                vectors.extend(await super().aembed_documents(batch))
            return vectors

    s = get_settings()
    return ThrottledMistralEmbeddings(
        model=s.mistral_embedding_model,
        api_key=s.mistral_api_key,
        # Batches by characters; avoids downloading a tokenizer from Hugging Face at startup.
        tokenizer=DummyTokenizer(),
        max_retries=5,
        wait_time=3,  # seconds between retries after a 429
    )


@lru_cache
def embeddings() -> Embeddings:
    from langchain_openai import OpenAIEmbeddings

    s = get_settings()
    if s.llm_provider == "cloudflare":
        return OpenAIEmbeddings(
            model=s.cloudflare_embedding_model,
            api_key=s.cloudflare_api_token,
            base_url=cloudflare_base_url(),
            check_embedding_ctx_length=False,  # send text, not OpenAI token ids
            chunk_size=50,  # texts per request
            # The OpenAI client otherwise asks for base64.
            model_kwargs={"encoding_format": "float"},
            max_retries=2,
        )
    if s.llm_provider == "mistral":
        return _mistral_embeddings()
    return OpenAIEmbeddings(
        model=s.openai_embedding_model,
        api_key=s.openai_api_key,
        dimensions=s.vector_size,
    )


def _status_code(exc: BaseException) -> int | None:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code
    return getattr(exc, "status_code", None)


def is_rate_limited(exc: BaseException) -> bool:
    return _status_code(exc) == 429 or "neurons" in str(exc).lower()


def ai_error_message(exc: BaseException) -> str | None:
    """A student-friendly message for AI-provider limits, or None for other errors."""
    text = str(exc).lower()
    if "neurons" in text or "daily free allocation" in text:
        return (
            "Today's free AI allowance is used up. It resets every day at 00:00 UTC "
            "(01:00 in Italy). Please come back then."
        )
    if is_rate_limited(exc):
        return "The AI service is busy right now. Please wait a few seconds and try again."
    return None
