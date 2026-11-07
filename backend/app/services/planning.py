"""Gathers everything the planner agent needs and asks it for a plan."""

from datetime import date, timedelta

from app.agents import planner
from app.schemas import StudyPlan
from app.services import mastery
from app.services.quizzes import due_flashcards
from supabase import AsyncClient

DEFAULT_DAYS = 7
MAX_DAYS = 14


async def upcoming_exams(db: AsyncClient, user_id: str, course_id: str) -> list[dict]:
    res = (
        await db.table("exams")
        .select("id, title, exam_date")
        .eq("user_id", user_id)
        .eq("course_id", course_id)
        .gte("exam_date", date.today().isoformat())
        .order("exam_date")
        .execute()
    )
    return res.data or []


def plan_dates(today: date, exams: list[dict], days: int | None) -> list[date]:
    """Plan until the next exam (inclusive of the day before), capped at MAX_DAYS."""
    if days is None:
        if exams:
            next_exam = date.fromisoformat(exams[0]["exam_date"])
            days = max(1, (next_exam - today).days)
        else:
            days = DEFAULT_DAYS
    days = max(1, min(days, MAX_DAYS))
    return [today + timedelta(days=i) for i in range(days)]


async def make_plan(
    db: AsyncClient,
    user_id: str,
    course_id: str,
    daily_minutes: int = 60,
    days: int | None = None,
) -> StudyPlan:
    today = date.today()
    exams = await upcoming_exams(db, user_id, course_id)
    return await planner.build_plan(
        today=today,
        dates=plan_dates(today, exams, days),
        daily_minutes=daily_minutes,
        mastery=await mastery.get_mastery(db, user_id, course_id),
        exams=exams,
        due_flashcards=len(await due_flashcards(db, user_id, course_id)),
    )


# Saved plans ----------------------------------------------------------------------
async def save_plan(
    db: AsyncClient, user_id: str, course_id: str, plan: StudyPlan | dict, daily_minutes: int = 60
) -> dict:
    data = plan.model_dump(mode="json") if isinstance(plan, StudyPlan) else plan
    res = await (
        db.table("study_plans")
        .insert(
            {
                "user_id": user_id,
                "course_id": course_id,
                "daily_minutes": daily_minutes,
                "summary": data["summary"],
                "days": data["days"],
            }
        )
        .execute()
    )
    return res.data[0]


async def list_plans(db: AsyncClient, user_id: str, course_id: str, limit: int = 50) -> list[dict]:
    res = (
        await db.table("study_plans")
        .select("id, daily_minutes, summary, days, created_at")
        .eq("user_id", user_id)
        .eq("course_id", course_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


async def delete_plan(db: AsyncClient, user_id: str, plan_id: str) -> None:
    await db.table("study_plans").delete().eq("id", plan_id).eq("user_id", user_id).execute()
