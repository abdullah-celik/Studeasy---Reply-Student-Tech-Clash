"""Vector search over a course's chunks (RAG)."""

import random

from app.config import get_settings
from app.llm import embeddings
from supabase import AsyncClient


async def search(
    db: AsyncClient, user_id: str, course_id: str, query: str, k: int | None = None
) -> list[dict]:
    vector = await embeddings().aembed_query(query)
    res = await db.rpc(
        "match_chunks",
        {
            "query_embedding": vector,
            "p_course_id": course_id,
            "p_user_id": user_id,
            "match_count": k or get_settings().retrieval_k,
        },
    ).execute()
    return res.data or []


async def sample_chunks(db: AsyncClient, user_id: str, course_id: str, n: int) -> list[dict]:
    """Random spread of chunks, used when a quiz/flashcards have no topic."""
    res = (
        await db.table("chunks")
        .select("id, document_id, content, location, documents(filename)")
        .eq("user_id", user_id)
        .eq("course_id", course_id)
        .limit(300)
        .execute()
    )
    rows = res.data or []
    picked = random.sample(rows, min(n, len(rows)))
    for r in picked:
        r["filename"] = (r.pop("documents", None) or {}).get("filename", "unknown")
    return picked


def format_sources(chunks: list[dict]) -> str:
    """Number the chunks so agents can cite them as [1], [2], ..."""
    return "\n\n".join(
        f"[{i}] ({c.get('filename', 'unknown')}, {c['location']})\n{c['content']}"
        for i, c in enumerate(chunks, start=1)
    )


def public_sources(chunks: list[dict], snippet_len: int = 240) -> list[dict]:
    return [
        {
            "index": i,
            "filename": c.get("filename", "unknown"),
            "location": c["location"],
            "snippet": c["content"][:snippet_len],
        }
        for i, c in enumerate(chunks, start=1)
    ]
