"""Fill in missing chunk embeddings.

Switching AI provider changes the embedding size, so the migration clears the old
vectors but keeps the chunk text. On startup the backend re-embeds those chunks in
the background, so students don't have to upload their files again.
"""

import logging

from app.llm import embeddings
from supabase import AsyncClient

log = logging.getLogger(__name__)

BATCH = 64
COLUMNS = "id, user_id, course_id, document_id, content, location"


async def backfill_embeddings(db: AsyncClient) -> int:
    done = 0
    failed_ids: set[str] = set()
    while True:
        res = (
            await db.table("chunks")
            .select(COLUMNS)
            .is_("embedding", "null")
            .limit(BATCH + len(failed_ids))
            .execute()
        )
        rows = [r for r in (res.data or []) if r["id"] not in failed_ids][:BATCH]
        if not rows:
            break
        try:
            vectors = await embeddings().aembed_documents([r["content"] for r in rows])
        except Exception:
            log.exception("Re-embedding a batch failed; skipping it until the next restart")
            failed_ids.update(r["id"] for r in rows)
            continue
        for row, vector in zip(rows, vectors, strict=True):
            row["embedding"] = vector
        await db.table("chunks").upsert(rows, on_conflict="id").execute()
        done += len(rows)
        log.info("Re-embedded %d chunks so far", done)
    if done:
        log.info("Re-embedding finished: %d chunks", done)
    return done
