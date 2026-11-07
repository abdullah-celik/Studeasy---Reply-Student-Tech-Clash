"""Reels feed: adaptive, generated on demand, with soft break nudges.

Feed logic
1. Return the student's unseen reels for the course, in generation order.
2. If fewer than a page are left, generate a batch:
   - up to 2 due flashcards become flip reels (no LLM call),
   - the weakest concept plus one random concept for variety each get a group of cards
     (explainer -> myth/mnemonic -> quiz -> flashcard), generated in parallel.
3. After every `reels_break_every` reels in a session, insert a synthetic "break" card.
"""

import asyncio
import logging
import random
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status

from app.agents import reels as reels_agent
from app.config import get_settings
from app.errors import NoMaterialError
from app.services import mastery, retrieval
from app.services.quizzes import due_flashcards
from supabase import AsyncClient

log = logging.getLogger(__name__)

CONCEPTS_PER_BATCH = 2
DUE_CARDS_PER_BATCH = 2
SOURCE_CHUNKS = 4


# Preferences (the per-student opt-in) ---------------------------------------
async def get_preferences(db: AsyncClient, user_id: str) -> dict:
    res = (
        await db.table("user_preferences")
        .select("reels_enabled")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else {"reels_enabled": False}


async def update_preferences(db: AsyncClient, user_id: str, changes: dict) -> dict:
    current = await get_preferences(db, user_id)
    row = {
        "user_id": user_id,
        **current,
        **changes,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    await db.table("user_preferences").upsert(row, on_conflict="user_id").execute()
    return {"reels_enabled": row["reels_enabled"]}


# Pure helpers (unit-tested) -------------------------------------------------
def pick_concepts(
    mastery_rows: list[dict],
    recent_counts: dict[str, int],
    n: int = CONCEPTS_PER_BATCH,
    rng: random.Random | None = None,
) -> list[str]:
    """Weakest concept first (ties: least recently shown, least practised), then random variety."""
    rng = rng or random.Random()
    if not mastery_rows:
        return []
    ranked = sorted(
        mastery_rows,
        key=lambda m: (m["score"], recent_counts.get(m["concept"], 0), m["attempts"]),
    )
    picks = [ranked[0]["concept"]]
    rest = [m["concept"] for m in ranked[1:]]
    while len(picks) < n and rest:
        picks.append(rest.pop(rng.randrange(len(rest))))
    return picks


def clean_quiz(q: reels_agent.QuizGen) -> dict | None:
    def norm(t: str) -> str:
        return " ".join(t.strip().lower().split())

    if q.kind == "true_false":
        answer = norm(q.answer)
        if answer not in {"true", "false"}:
            return None
        options = ["true", "false"]
    else:
        match = next((o for o in q.options if norm(o) == norm(q.answer)), None)
        if match is None or len(q.options) < 2:
            return None
        options, answer = q.options, match
    return {
        "question": q.question,
        "kind": q.kind,
        "options": options,
        "answer": answer,
        "explanation": q.explanation,
    }


def arrange(groups: list[list[dict]], due_rows: list[dict]) -> list[dict]:
    """Concept groups in order; due flashcards slotted in after the first group."""
    out: list[dict] = []
    for i, group in enumerate(groups):
        out.extend(group)
        if i == 0:
            out.extend(due_rows)
    if not groups:
        out.extend(due_rows)
    return out


def insert_break(items: list[dict], session_reels: int, break_every: int, stats: dict) -> list[dict]:
    """Insert at most one break card at the point where the session crosses a multiple."""
    if break_every <= 0:
        return items
    for i in range(len(items)):
        watched = session_reels + i
        if watched > 0 and watched % break_every == 0:
            concepts = stats.get("concepts", [])[:5]
            card = {
                "type": "break",
                "content": {
                    "title": "Nice streak — time for a breather?",
                    "message": (
                        f"You've gone through {watched} reels in {stats.get('minutes', 0)} min. "
                        "Stretch, drink some water, or try a quick quiz to lock it in. "
                        "Swipe to keep going whenever you're ready."
                    ),
                    "reels_watched": watched,
                    "minutes": stats.get("minutes", 0),
                    "concepts": concepts,
                },
            }
            return [*items[:i], card, *items[i:]]
    return items


REEL_ROW_DEFAULTS = {"source_chunk_ids": [], "flashcard_id": None}


def normalise_rows(rows: list[dict]) -> list[dict]:
    """A bulk insert uses the union of all keys and sends NULL for missing ones, which
    breaks NOT NULL columns, so every row gets the same keys with proper defaults."""
    return [{**REEL_ROW_DEFAULTS, **r} for r in rows]


# Database-backed logic -------------------------------------------------------
async def _unseen(db: AsyncClient, user_id: str, course_id: str, limit: int) -> list[dict]:
    res = (
        await db.table("reels")
        .select("id, type, concept, content")
        .eq("user_id", user_id)
        .eq("course_id", course_id)
        .is_("seen_at", "null")
        .order("seq")
        .limit(limit)
        .execute()
    )
    return res.data or []


async def session_stats(db: AsyncClient, user_id: str, course_id: str) -> dict:
    window = get_settings().reels_session_minutes
    since = (datetime.now(UTC) - timedelta(minutes=window)).isoformat()
    res = (
        await db.table("reel_views")
        .select("created_at, reels!inner(concept, course_id)")
        .eq("user_id", user_id)
        .eq("reels.course_id", course_id)
        .gte("created_at", since)
        .order("created_at")
        .execute()
    )
    rows = res.data or []
    if not rows:
        return {"count": 0, "minutes": 0, "concepts": []}
    first = datetime.fromisoformat(rows[0]["created_at"].replace("Z", "+00:00"))
    minutes = max(1, round((datetime.now(UTC) - first).total_seconds() / 60))
    concepts = list(dict.fromkeys(r["reels"]["concept"] for r in rows))
    return {"count": len(rows), "minutes": minutes, "concepts": concepts}


async def _concept_group(
    db: AsyncClient, user_id: str, course_id: str, concept: str | None
) -> list[dict]:
    chunks = (
        await retrieval.search(db, user_id, course_id, concept, k=SOURCE_CHUNKS)
        if concept
        else await retrieval.sample_chunks(db, user_id, course_id, SOURCE_CHUNKS)
    )
    if not chunks:
        raise NoMaterialError()
    gen = await reels_agent.generate(concept, retrieval.format_sources(chunks))
    name = concept or gen.concept
    base = {
        "user_id": user_id,
        "course_id": course_id,
        "concept": name,
        "source_chunk_ids": [c["id"] for c in chunks],
    }

    rows = [{**base, "type": "explainer", "content": gen.explainer.model_dump()}]
    if gen.myth_fact:
        rows.append({**base, "type": "myth_fact", "content": gen.myth_fact.model_dump()})
    elif gen.mnemonic:
        rows.append({**base, "type": "mnemonic", "content": gen.mnemonic.model_dump()})
    quiz = clean_quiz(gen.quiz)
    if quiz:
        rows.append({**base, "type": "quiz", "content": quiz})

    # Flip reels are real deck cards, so rating them feeds SM-2.
    card = (
        await db.table("flashcards")
        .insert(
            {
                "user_id": user_id,
                "course_id": course_id,
                "concept": name,
                **gen.flashcard.model_dump(),
            }
        )
        .execute()
    ).data[0]
    rows.append(
        {
            **base,
            "type": "flashcard",
            "flashcard_id": card["id"],
            "content": {"flashcard_id": card["id"], "front": card["front"], "back": card["back"]},
        }
    )
    return rows


async def _due_card_rows(
    db: AsyncClient, user_id: str, course_id: str, exclude: set[str]
) -> list[dict]:
    due = await due_flashcards(db, user_id, course_id, limit=10)
    if not due:
        return []
    queued = (
        await db.table("reels")
        .select("flashcard_id")
        .eq("user_id", user_id)
        .eq("course_id", course_id)
        .is_("seen_at", "null")
        .not_.is_("flashcard_id", "null")
        .execute()
    ).data or []
    # skip cards already queued as reels, and cards this batch just created (they're due now)
    already = {r["flashcard_id"] for r in queued} | exclude
    return [
        {
            "user_id": user_id,
            "course_id": course_id,
            "type": "flashcard",
            "concept": c["concept"],
            "flashcard_id": c["id"],
            "source_chunk_ids": [],
            "content": {"flashcard_id": c["id"], "front": c["front"], "back": c["back"]},
        }
        for c in due
        if c["id"] not in already
    ][:DUE_CARDS_PER_BATCH]


async def generate_batch(db: AsyncClient, user_id: str, course_id: str) -> int:
    since = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    recent = (
        await db.table("reels")
        .select("concept")
        .eq("user_id", user_id)
        .eq("course_id", course_id)
        .gte("created_at", since)
        .execute()
    ).data or []
    recent_counts: dict[str, int] = {}
    for r in recent:
        recent_counts[r["concept"]] = recent_counts.get(r["concept"], 0) + 1

    concepts = pick_concepts(await mastery.get_mastery(db, user_id, course_id), recent_counts)
    results = await asyncio.gather(
        *(_concept_group(db, user_id, course_id, c) for c in (concepts or [None])),
        return_exceptions=True,
    )
    groups = [r for r in results if not isinstance(r, BaseException)]
    errors = [r for r in results if isinstance(r, BaseException)]
    for e in errors:
        log.warning("Reel generation failed: %r", e)

    new_cards = {r["flashcard_id"] for g in groups for r in g if r.get("flashcard_id")}
    due_rows = await _due_card_rows(db, user_id, course_id, exclude=new_cards)
    rows = normalise_rows(arrange(groups, due_rows))
    if not rows:
        raise errors[0] if errors else NoMaterialError()
    await db.table("reels").insert(rows).execute()
    return len(rows)


async def get_feed(db: AsyncClient, user_id: str, course_id: str, limit: int) -> dict:
    items = await _unseen(db, user_id, course_id, limit)
    if len(items) < limit:
        await generate_batch(db, user_id, course_id)
        items = await _unseen(db, user_id, course_id, limit)
    stats = await session_stats(db, user_id, course_id)
    break_every = get_settings().reels_break_every
    return {
        "items": insert_break(items, stats["count"], break_every, stats),
        "session_reels": stats["count"],
        "break_every": break_every,
    }


async def _owned_reel(db: AsyncClient, user_id: str, reel_id: str) -> dict:
    res = (
        await db.table("reels")
        .select("*")
        .eq("id", reel_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reel not found")
    return res.data[0]


async def record_view(
    db: AsyncClient, user_id: str, reel_id: str, watch_ms: int, completed: bool
) -> None:
    reel = await _owned_reel(db, user_id, reel_id)
    await (
        db.table("reel_views")
        .insert(
            {"user_id": user_id, "reel_id": reel_id, "watch_ms": watch_ms, "completed": completed}
        )
        .execute()
    )
    if reel["seen_at"] is None:
        await (
            db.table("reels")
            .update({"seen_at": datetime.now(UTC).isoformat()})
            .eq("id", reel_id)
            .execute()
        )


async def answer_quiz(db: AsyncClient, user_id: str, reel_id: str, response: str) -> dict:
    reel = await _owned_reel(db, user_id, reel_id)
    if reel["type"] != "quiz":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This reel is not a quiz")
    content = reel["content"]
    correct = " ".join(response.strip().lower().split()) == " ".join(
        content["answer"].strip().lower().split()
    )
    await mastery.record_result(db, user_id, reel["course_id"], reel["concept"], float(correct))
    return {
        "correct": correct,
        "correct_answer": content["answer"],
        "explanation": content["explanation"],
    }
