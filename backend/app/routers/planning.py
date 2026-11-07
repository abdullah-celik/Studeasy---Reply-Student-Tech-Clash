from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.db import get_db
from app.deps import CurrentUser, get_current_user, get_owned_course
from app.schemas import Exam, ExamCreate, MasteryItem, PlanCreate, SavedPlan, StudyPlan
from app.services import mastery, planning
from supabase import AsyncClient

router = APIRouter(prefix="/courses/{course_id}", tags=["planning"])


@router.post("/exams", response_model=Exam, status_code=status.HTTP_201_CREATED)
async def create_exam(
    body: ExamCreate,
    course: dict = Depends(get_owned_course),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    res = await (
        db.table("exams")
        .insert(
            {
                "user_id": user.id,
                "course_id": course["id"],
                "title": body.title,
                "exam_date": body.exam_date.isoformat(),
            }
        )
        .execute()
    )
    return res.data[0]


@router.get("/exams", response_model=list[Exam])
async def list_exams(
    course: dict = Depends(get_owned_course),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    return await planning.upcoming_exams(db, user.id, course["id"])


@router.delete("/exams/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exam(
    exam_id: UUID,
    course: dict = Depends(get_owned_course),
    db: AsyncClient = Depends(get_db),
):
    await db.table("exams").delete().eq("id", str(exam_id)).eq("course_id", course["id"]).execute()


@router.get("/mastery", response_model=list[MasteryItem])
async def get_mastery(
    course: dict = Depends(get_owned_course),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    return await mastery.get_mastery(db, user.id, course["id"])


@router.get("/plan", response_model=StudyPlan)
async def get_plan(
    daily_minutes: int = Query(60, ge=15, le=600),
    days: int | None = Query(None, ge=1, le=14, description="Defaults to until the next exam"),
    course: dict = Depends(get_owned_course),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    return await planning.make_plan(db, user.id, course["id"], daily_minutes, days)


@router.post("/plans", response_model=SavedPlan, status_code=status.HTTP_201_CREATED)
async def create_plan(
    body: PlanCreate,
    course: dict = Depends(get_owned_course),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Like GET /plan, but the plan is stored so it shows up in the plan history."""
    plan = await planning.make_plan(db, user.id, course["id"], body.daily_minutes, body.days)
    return await planning.save_plan(db, user.id, course["id"], plan, body.daily_minutes)


@router.get("/plans", response_model=list[SavedPlan])
async def list_plans(
    course: dict = Depends(get_owned_course),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    return await planning.list_plans(db, user.id, course["id"])


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(
    plan_id: UUID,
    course: dict = Depends(get_owned_course),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    await planning.delete_plan(db, user.id, plan_id=str(plan_id))
