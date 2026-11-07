from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.db import get_db
from app.deps import CurrentUser, get_current_user, get_owned_course
from app.schemas import Flashcard, FlashcardDeck, FlashcardGenerate, ReviewSubmit
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


@router.get("/courses/{course_id}/flashcards/decks", response_model=list[FlashcardDeck])
async def list_decks(
    course: dict = Depends(get_owned_course),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """One deck per generation, newest first."""
    return await quizzes.list_decks(db, user.id, course["id"])


@router.get("/flashcards/decks/{deck_id}", response_model=list[Flashcard])
async def deck_cards(
    deck_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    return await quizzes.deck_cards(db, user.id, str(deck_id))


@router.delete("/flashcards/decks/{deck_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deck(
    deck_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    await quizzes.delete_deck(db, user.id, str(deck_id))
