"""Mastery map: a 0..1 confidence score per concept, updated after every quiz answer
or flashcard review. It's what links the quiz master, planner and tutor together."""

from datetime import UTC, datetime

from supabase import AsyncClient

# Weight of the newest result in the moving average.
ALPHA = 0.3


def updated_score(old_score: float, attempts: int, result: float) -> float:
    if attempts == 0:
        return result
    return round((1 - ALPHA) * old_score + ALPHA * result, 4)


async def record_result(
    db: AsyncClient, user_id: str, course_id: str, concept: str, result: float
) -> None:
    concept = concept.strip()
    if not concept:
        return
    res = (
        await db.table("mastery")
        .select("id, score, attempts")
        .eq("user_id", user_id)
        .eq("course_id", course_id)
        .eq("concept", concept)
        .limit(1)
        .execute()
    )
    now = datetime.now(UTC).isoformat()
    if res.data:
        row = res.data[0]
        await (
            db.table("mastery")
            .update(
                {
                    "score": updated_score(row["score"], row["attempts"], result),
                    "attempts": row["attempts"] + 1,
                    "updated_at": now,
                }
            )
            .eq("id", row["id"])
            .execute()
        )
    else:
        await (
            db.table("mastery")
            .insert(
                {
                    "user_id": user_id,
                    "course_id": course_id,
                    "concept": concept,
                    "score": result,
                    "attempts": 1,
                    "updated_at": now,
                }
            )
            .execute()
        )


async def seed_concepts(db: AsyncClient, user_id: str, course_id: str, concepts: list[str]) -> None:
    """Add newly discovered concepts with score 0 (existing ones are left untouched)."""
    rows = [
        {"user_id": user_id, "course_id": course_id, "concept": c.strip()}
        for c in dict.fromkeys(concepts)
        if c.strip()
    ]
    if rows:
        await (
            db.table("mastery")
            .upsert(rows, on_conflict="user_id,course_id,concept", ignore_duplicates=True)
            .execute()
        )


async def get_mastery(db: AsyncClient, user_id: str, course_id: str) -> list[dict]:
    res = (
        await db.table("mastery")
        .select("concept, score, attempts")
        .eq("user_id", user_id)
        .eq("course_id", course_id)
        .order("score")
        .execute()
    )
    return res.data or []
