from functools import lru_cache

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import BaseModel

from app.config import get_settings


@lru_cache
def chat_model() -> ChatOpenAI:
    s = get_settings()
    kwargs = {}
    if s.openai_temperature is not None:
        kwargs["temperature"] = s.openai_temperature
    return ChatOpenAI(
        model=s.openai_chat_model,
        api_key=s.openai_api_key,
        streaming=True,
        **kwargs,
    )


def structured(schema: type[BaseModel]):
    """Chat model that returns a validated Pydantic object.

    function_calling is used instead of strict json_schema because strict mode
    rejects optional fields / defaults, which our schemas use.
    """
    return chat_model().with_structured_output(schema, method="function_calling")


@lru_cache
def embeddings() -> OpenAIEmbeddings:
    s = get_settings()
    return OpenAIEmbeddings(
        model=s.openai_embedding_model,
        api_key=s.openai_api_key,
        dimensions=s.embedding_dimensions,
    )
