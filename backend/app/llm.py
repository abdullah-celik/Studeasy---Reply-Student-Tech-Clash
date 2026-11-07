from functools import lru_cache

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import BaseModel

from app.config import get_settings


@lru_cache
def _model(reasoning_effort: str | None) -> ChatOpenAI:
    s = get_settings()
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


def chat_model() -> ChatOpenAI:
    """Free-text answers (tutor): uses OPENAI_REASONING_EFFORT."""
    return _model(get_settings().openai_reasoning_effort)


def structured(schema: type[BaseModel]):
    """Chat model that returns a validated Pydantic object.

    function_calling is used instead of strict json_schema because strict mode
    rejects optional fields / defaults, which our schemas use. For GPT-6 models LangChain
    routes tool calls through the Responses API; effort comes from
    OPENAI_STRUCTURED_REASONING_EFFORT ("none" by default: fast and cheap).
    """
    model = _model(get_settings().openai_structured_reasoning_effort)
    # One retry: if the model returns something that fails validation, ask again.
    return model.with_structured_output(schema, method="function_calling").with_retry(
        stop_after_attempt=2
    )


@lru_cache
def embeddings() -> OpenAIEmbeddings:
    s = get_settings()
    return OpenAIEmbeddings(
        model=s.openai_embedding_model,
        api_key=s.openai_api_key,
        dimensions=s.embedding_dimensions,
    )
