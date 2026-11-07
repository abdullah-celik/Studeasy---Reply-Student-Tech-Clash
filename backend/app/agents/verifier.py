"""Verifier agent: checks the tutor's answer against the retrieved sources."""

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from app.llm import structured

SYSTEM = """You fact-check a tutor's answer against numbered SOURCES.
Claims explicitly labelled "(not from your course material)" are allowed and not unsupported.
Return grounded=true if every other factual claim is supported by the sources.
List any unsupported or contradicted claims briefly."""


class Verification(BaseModel):
    grounded: bool
    unsupported_claims: list[str] = Field(default_factory=list)


async def verify(
    answer: str, sources_text: str, config: RunnableConfig | None = None
) -> Verification:
    msgs = [
        ("system", SYSTEM),
        ("human", f"SOURCES:\n{sources_text}\n\nANSWER:\n{answer}"),
    ]
    return await structured(Verification).ainvoke(msgs, config=config)
