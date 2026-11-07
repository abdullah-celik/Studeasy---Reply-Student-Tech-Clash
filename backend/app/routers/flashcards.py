from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.db import get_db
from app.deps import CurrentUser, get_current_user, get_owned_course
from app.schemas import Flashcard, FlashcardGenerate, ReviewSubmit
from app.services import quizzes
from supabase import AsyncClient

router = APIRouter(tags=["flashcards"])


@router.post(
    "/courses/{course_id}/flashcards",
    response_model=list[Flashcard],
    status_code=status.HTTP_201_CREATED,
)
async def generate_flashcards(
    body: FlashcardGenerate,
    course: dict = Depends(get_owned_course),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    return await quizzes.create_flashcards(db, user.id, course["id"], body.topic, body.count)


@router.get("/courses/{course_id}/flashcards/due", response_model=list[Flashcard])
async def due_flashcards(
    course: dict = Depends(get_owned_course),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    return await quizzes.due_flashcards(db, user.id, course["id"])


@router.post("/flashcards/{card_id}/review", response_model=Flashcard)
async def review_flashcard(
    card_id: UUID,
    body: ReviewSubmit,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    return await quizzes.review_flashcard(db, user.id, str(card_id), body.quality)
