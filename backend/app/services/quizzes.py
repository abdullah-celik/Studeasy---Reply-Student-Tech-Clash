"""Quiz & flashcard workflows (used by both the REST endpoints and the chat graph)."""

import logging
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status

from app.agents import quiz as quiz_agent
from app.errors import NoMaterialError
from app.schemas import QuestionType
from app.services import mastery, retrieval, sm2
from supabase import AsyncClient

log = logging.getLogger(__name__)

SOURCE_CHUNKS = 8
PASS_THRESHOLD = 0.6


async def _material(db: AsyncClient, user_id: str, course_id: str, topic: str | None) -> list[dict]:
    chunks = (
        await retrieval.search(db, user_id, course_id, topic, k=SOURCE_CHUNKS)
        if topic
        else await retrieval.sample_chunks(db, user_id, course_id, SOURCE_CHUNKS)
    )
    if not chunks:
        raise NoMaterialError()
    return chunks


async def _known_concepts(db: AsyncClient, user_id: str, course_id: str) -> list[str]:
    return [m["concept"] for m in await mastery.get_mastery(db, user_id, course_id)]


def _normalise(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _clean_question(q: quiz_agent.GeneratedQuestion, allowed: set[str]) -> dict | None:
    """Drop or repair malformed LLM output instead of showing a broken question."""
    if q.type not in allowed:
        return None
    if q.type == "true_false":
        answer = _normalise(q.answer)
        if answer not in {"true", "false"}:
            return None
        return {"options": ["true", "false"], "answer": answer}
    if q.type == "multiple_choice":
        if len(q.options) < 2:
            return None
        match = next((o for o in q.options if _normalise(o) == _normalise(q.answer)), None)
        if match is None:
            return None
        return {"options": q.options, "answer": match}
    return {"options": [], "answer": q.answer}


async def create_quiz(
    db: AsyncClient,
    user_id: str,
    course_id: str,
    topic: str | None,
    types: list[QuestionType],
    count: int,
) -> dict:
    chunks = await _material(db, user_id, course_id, topic)
    generated = await quiz_agent.generate_questions(
        retrieval.format_sources(chunks),
        types,
        count,
        topic,
        await _known_concepts(db, user_id, course_id),
    )

    quiz = (
        await db.table("quizzes")
        .insert({"user_id": user_id, "course_id": course_id, "topic": topic})
        .execute()
    ).data[0]

    rows = []
    for q in generated.questions:
        cleaned = _clean_question(q, set(types))
        if cleaned is None:
            log.warning("Dropped malformed question: %s", q.prompt[:80])
            continue
        source_ids = [chunks[i - 1]["id"] for i in q.source_indices if 1 <= i <= len(chunks)]
        rows.append(
            {
                "user_id": user_id,
                "quiz_id": quiz["id"],
                "type": q.type,
                "prompt": q.prompt,
                "explanation": q.explanation,
                "concept": q.concept,
                "source_chunk_ids": source_ids,
                "position": len(rows),
                **cleaned,
            }
        )
        if len(rows) == count:
            break

    inserted = (await db.table("questions").insert(rows).execute()).data if rows else []
    return {
        "id": quiz["id"],
        "course_id": course_id,
        "topic": topic,
        "created_at": quiz["created_at"],
        "questions": [
            {k: r[k] for k in ("id", "type", "prompt", "options", "concept")} for r in inserted
        ],
    }


async def get_quiz(db: AsyncClient, user_id: str, quiz_id: str) -> dict:
    res = (
        await db.table("quizzes")
        .select("id, course_id, topic, created_at, "
                "questions(id, type, prompt, options, concept, position)")
        .eq("id", quiz_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quiz not found")
    quiz = res.data[0]
    quiz["questions"] = sorted(quiz["questions"], key=lambda q: q["position"])
    return quiz


async def submit_answer(
    db: AsyncClient, user_id: str, quiz_id: str, question_id: str, response: str
) -> dict:
    res = (
        await db.table("questions")
        .select("*, quizzes(course_id)")
        .eq("id", question_id)
        .eq("quiz_id", quiz_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")
    q = res.data[0]
    course_id = q["quizzes"]["course_id"]

    if q["type"] in ("multiple_choice", "true_false"):
        correct = _normalise(response) == _normalise(q["answer"])
        score = 1.0 if correct else 0.0
        feedback = "Correct!" if correct else "Not quite."
    else:
        sources_text = ""
        if q["source_chunk_ids"]:
            chunks = (
                await db.table("chunks")
                .select("content, location")
                .in_("id", q["source_chunk_ids"])
                .execute()
            ).data or []
            sources_text = "\n\n".join(f"({c['location']}) {c['content']}" for c in chunks)
        grade = await quiz_agent.grade_open_answer(q["prompt"], q["answer"], response, sources_text)
        score = grade.score
        correct = score >= PASS_THRESHOLD
        feedback = grade.feedback

    await (
        db.table("answers")
        .insert(
            {
                "user_id": user_id,
                "question_id": question_id,
                "response": response,
                "correct": correct,
                "score": score,
                "feedback": feedback,
            }
        )
        .execute()
    )
    await mastery.record_result(db, user_id, course_id, q["concept"], score)

    return {
        "question_id": question_id,
        "correct": correct,
        "score": score,
        "feedback": feedback,
        "correct_answer": q["answer"],
        "explanation": q["explanation"],
    }


# Quiz history ---------------------------------------------------------------
def _latest(answers: list[dict]) -> dict | None:
    return max(answers, key=lambda a: a["created_at"]) if answers else None


def summarize_quiz(row: dict) -> dict:
    """Question count, how many are answered and the mean of the latest score per question."""
    questions = row.get("questions") or []
    latest = [a for q in questions if (a := _latest(q.get("answers") or []))]
    return {
        "id": row["id"],
        "topic": row.get("topic"),
        "created_at": row["created_at"],
        "question_count": len(questions),
        "answered_count": len(latest),
        "score": sum(a["score"] for a in latest) / len(latest) if latest else None,
    }


async def list_quizzes(db: AsyncClient, user_id: str, course_id: str, limit: int = 100) -> list[dict]:
    res = (
        await db.table("quizzes")
        .select("id, topic, created_at, questions(id, answers(score, created_at))")
        .eq("user_id", user_id)
        .eq("course_id", course_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [summarize_quiz(r) for r in res.data or []]


async def quiz_answers(db: AsyncClient, user_id: str, quiz_id: str) -> list[dict]:
    """Latest result per answered question, so a reopened quiz shows its earlier answers."""
    res = (
        await db.table("questions")
        .select("id, answer, explanation, answers(correct, score, feedback, created_at)")
        .eq("quiz_id", quiz_id)
        .eq("user_id", user_id)
        .execute()
    )
    out = []
    for q in res.data or []:
        a = _latest(q.get("answers") or [])
        if a:
            out.append(
                {
                    "question_id": q["id"],
                    "correct": a["correct"],
                    "score": a["score"],
                    "feedback": a["feedback"],
                    "correct_answer": q["answer"],
                    "explanation": q["explanation"],
                }
            )
    return out


async def delete_quiz(db: AsyncClient, user_id: str, quiz_id: str) -> None:
    await db.table("quizzes").delete().eq("id", quiz_id).eq("user_id", user_id).execute()


# Flashcards ----------------------------------------------------------------
async def create_flashcards(
    db: AsyncClient, user_id: str, course_id: str, topic: str | None, count: int
) -> list[dict]:
    chunks = await _material(db, user_id, course_id, topic)
    deck = await quiz_agent.generate_flashcards(
        retrieval.format_sources(chunks),
        count,
        topic,
        await _known_concepts(db, user_id, course_id),
    )
    cards = deck.cards[:count]
    if not cards:
        return []
    deck_row = (
        await db.table("flashcard_decks")
        .insert({"user_id": user_id, "course_id": course_id, "topic": topic})
        .execute()
    ).data[0]
    rows = [
        {"user_id": user_id, "course_id": course_id, "deck_id": deck_row["id"], **c.model_dump()}
        for c in cards
    ]
    return (await db.table("flashcards").insert(rows).execute()).data


def summarize_deck(row: dict, now: datetime) -> dict:
    cards = row.get("flashcards") or []
    return {
        "id": row["id"],
        "topic": row.get("topic"),
        "created_at": row["created_at"],
        "card_count": len(cards),
        "due_count": sum(1 for c in cards if datetime.fromisoformat(c["due_at"]) <= now),
    }


async def list_decks(db: AsyncClient, user_id: str, course_id: str) -> list[dict]:
    res = (
        await db.table("flashcard_decks")
        .select("id, topic, created_at, flashcards(due_at)")
        .eq("user_id", user_id)
        .eq("course_id", course_id)
        .order("created_at", desc=True)
        .execute()
    )
    now = datetime.now(UTC)
    return [summarize_deck(r, now) for r in res.data or []]


async def deck_cards(db: AsyncClient, user_id: str, deck_id: str) -> list[dict]:
    res = (
        await db.table("flashcards")
        .select("*")
        .eq("deck_id", deck_id)
        .eq("user_id", user_id)
        .order("created_at")
        .execute()
    )
    if not res.data:
        exists = (
            await db.table("flashcard_decks").select("id").eq("id", deck_id)
            .eq("user_id", user_id).limit(1).execute()
        )
        if not exists.data:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Deck not found")
    return res.data or []


async def delete_deck(db: AsyncClient, user_id: str, deck_id: str) -> None:
    await db.table("flashcard_decks").delete().eq("id", deck_id).eq("user_id", user_id).execute()


async def due_flashcards(db: AsyncClient, user_id: str, course_id: str, limit: int = 50) -> list[dict]:
    now = datetime.now(UTC).isoformat()
    res = (
        await db.table("flashcards")
        .select("*")
        .eq("user_id", user_id)
        .eq("course_id", course_id)
        .lte("due_at", now)
        .order("due_at")
        .limit(limit)
        .execute()
    )
    return res.data or []


async def review_flashcard(db: AsyncClient, user_id: str, card_id: str, quality: int) -> dict:
    res = (
        await db.table("flashcards")
        .select("*")
        .eq("id", card_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Flashcard not found")
    card = res.data[0]

    new = sm2.review(
        sm2.SM2State(card["ease"], card["interval"], card["repetitions"]), quality
    )
    due_at = datetime.now(UTC) + timedelta(days=new.interval)
    updated = (
        await db.table("flashcards")
        .update(
            {
                "ease": new.ease,
                "interval": new.interval,
                "repetitions": new.repetitions,
                "due_at": due_at.isoformat(),
            }
        )
        .eq("id", card_id)
        .execute()
    ).data[0]
    await mastery.record_result(db, user_id, card["course_id"], card["concept"], quality / 5)
    return updated
