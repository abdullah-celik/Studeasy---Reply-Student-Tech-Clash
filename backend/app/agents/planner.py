"""Planner agent: turns mastery scores, exams and due flashcards into a day-by-day plan."""

from datetime import date

from app.llm import structured
from app.schemas import StudyPlan

SYSTEM = """You are a study coach. Build a realistic day-by-day study plan.

Rules:
- Plan exactly the dates listed in DATES, in order, about {daily_minutes} minutes per day.
- Prioritise concepts with the lowest mastery score, and concepts never practised.
- Put a "review_flashcards" task first on any day with due cards (about 10-15 min).
- Use "quiz" tasks to check weak concepts after studying them.
- Intensify before exams; include a light day or "rest" task for long plans.
- `note`: one short, concrete instruction per task.
- `summary`: 2-3 encouraging sentences explaining the strategy."""


async def build_plan(
    today: date,
    dates: list[date],
    daily_minutes: int,
    mastery: list[dict],
    exams: list[dict],
    due_flashcards: int,
) -> StudyPlan:
    mastery_lines = "\n".join(
        f"- {m['concept']}: score {m['score']:.2f}, practised {m['attempts']}x" for m in mastery
    ) or "- (no concepts yet)"
    exam_lines = "\n".join(f"- {e['title']} on {e['exam_date']}" for e in exams) or "- none"
    human = (
        f"TODAY: {today.isoformat()}\n"
        f"DATES: {', '.join(d.isoformat() for d in dates)}\n"
        f"FLASHCARDS DUE NOW: {due_flashcards}\n\n"
        f"UPCOMING EXAMS:\n{exam_lines}\n\nMASTERY (lowest first):\n{mastery_lines}"
    )
    system = SYSTEM.format(daily_minutes=daily_minutes)
    return await structured(StudyPlan).ainvoke([("system", system), ("human", human)])
