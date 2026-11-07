from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.db import get_db
from app.deps import CurrentUser, get_current_user, get_owned_course
from app.schemas import AnswerResult, AnswerSubmit, Quiz, QuizCreate
from app.services import quizzes
from supabase import AsyncClient

router = APIRouter(tags=["quizzes"])


@router.post(
    "/courses/{course_id}/quizzes", response_model=Quiz, status_code=status.HTTP_201_CREATED
)
async def create_quiz(
    body: QuizCreate,
    course: dict = Depends(get_owned_course),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    return await quizzes.create_quiz(
        db, user.id, course["id"], body.topic, list(dict.fromkeys(body.types)), body.count
    )


@router.get("/quizzes/{quiz_id}", response_model=Quiz)
async def get_quiz(
    quiz_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    return await quizzes.get_quiz(db, user.id, str(quiz_id))


@router.post("/quizzes/{quiz_id}/answers", response_model=AnswerResult)
async def submit_answer(
    quiz_id: UUID,
    body: AnswerSubmit,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    return await quizzes.submit_answer(
        db, user.id, str(quiz_id), str(body.question_id), body.response
    )
