"""Content agent: reads newly ingested material and names its key concepts."""

from pydantic import BaseModel, Field

from app.llm import structured

MAX_CHARS = 12_000

SYSTEM = (
    "You analyse university course material. List the key concepts a student must master "
    "to pass an exam on it. Use short, canonical names (2-5 words), no duplicates, "
    "most important first."
)


class ConceptList(BaseModel):
    concepts: list[str] = Field(description="Up to 15 key concepts")


def _spread_sample(texts: list[str], max_chars: int = MAX_CHARS) -> str:
    """Take chunks evenly from the whole document rather than only its beginning."""
    if not texts:
        return ""
    per_chunk = max(1, len(texts[0]))
    n = max(1, max_chars // per_chunk)
    step = max(1, len(texts) // n)
    return "\n---\n".join(texts[::step])[:max_chars]


async def extract_concepts(texts: list[str]) -> list[str]:
    sample = _spread_sample(texts)
    if not sample.strip():
        return []
    result: ConceptList = await structured(ConceptList).ainvoke(
        [("system", SYSTEM), ("human", sample)]
    )
    return result.concepts[:15]
