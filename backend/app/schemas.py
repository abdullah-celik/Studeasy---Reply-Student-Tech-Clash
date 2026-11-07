"""Request/response models.

These are the API contract with the TypeScript frontend: FastAPI turns them into
/openapi.json, from which the frontend generates its types (see docs/FRONTEND.md).
"""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

QuestionType = Literal["multiple_choice", "true_false", "open"]
DocumentStatus = Literal["processing", "ready", "failed"]


# Courses & documents ------------------------------------------------------
class CourseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class Course(BaseModel):
    id: UUID
    name: str
    description: str | None
    created_at: datetime


class Document(BaseModel):
    id: UUID
    course_id: UUID
    filename: str
    status: DocumentStatus
    chunk_count: int
    error: str | None
    created_at: datetime


# Chat ---------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    chat_id: UUID | None = Field(
        None, description="Thread to continue (POST /courses/{id}/chats). Omit for the legacy single thread."
    )


class ChatThread(BaseModel):
    id: UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class ChatThreadCreate(BaseModel):
    title: str | None = Field(None, max_length=200)


class ChatThreadUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class ChatMessage(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class Source(BaseModel):
    index: int  # the [n] the tutor cites
    filename: str
    location: str
    snippet: str


# Quizzes ------------------------------------------------------------------
class QuizCreate(BaseModel):
    topic: str | None = Field(None, description="Focus topic; omit to sample the whole course")
    types: list[QuestionType] = ["multiple_choice", "true_false", "open"]
    count: int = Field(5, ge=1, le=20)


class QuestionPublic(BaseModel):
    """A question as the student sees it: no answer, no explanation."""

    id: UUID
    type: QuestionType
    prompt: str
    options: list[str]
    concept: str


class Quiz(BaseModel):
    id: UUID
    course_id: UUID
    topic: str | None
    created_at: datetime
    questions: list[QuestionPublic]


class QuizSummary(BaseModel):
    id: UUID
    topic: str | None
    created_at: datetime
    question_count: int
    answered_count: int
    score: float | None = Field(None, description="Mean of the latest score per answered question")


class AnswerSubmit(BaseModel):
    question_id: UUID
    response: str = Field(min_length=1, max_length=4000)


class AnswerResult(BaseModel):
    question_id: UUID
    correct: bool
    score: float = Field(ge=0, le=1)
    feedback: str
    correct_answer: str
    explanation: str


# Flashcards ---------------------------------------------------------------
class FlashcardGenerate(BaseModel):
    topic: str | None = None
    count: int = Field(10, ge=1, le=40)


class Flashcard(BaseModel):
    id: UUID
    deck_id: UUID | None = None
    front: str
    back: str
    concept: str
    ease: float
    interval: int
    repetitions: int
    due_at: datetime


class FlashcardDeck(BaseModel):
    id: UUID
    topic: str | None
    created_at: datetime
    card_count: int
    due_count: int


class ReviewSubmit(BaseModel):
    quality: int = Field(
        ge=0, le=5, description="SM-2 grade: 0 = blackout ... 5 = perfect recall"
    )


# Planning -----------------------------------------------------------------
class ExamCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    exam_date: date


class Exam(BaseModel):
    id: UUID
    title: str
    exam_date: date


class MasteryItem(BaseModel):
    concept: str
    score: float
    attempts: int


class PlanTask(BaseModel):
    kind: Literal["review_flashcards", "quiz", "study", "rest"]
    concept: str | None = None
    minutes: int = Field(ge=0, le=600)
    note: str


class PlanDay(BaseModel):
    date: date
    tasks: list[PlanTask]


class StudyPlan(BaseModel):
    summary: str
    days: list[PlanDay]


class PlanCreate(BaseModel):
    daily_minutes: int = Field(60, ge=15, le=600)
    days: int | None = Field(None, ge=1, le=14, description="Defaults to until the next exam")


class SavedPlan(StudyPlan):
    id: UUID
    daily_minutes: int
    created_at: datetime


# Reels ----------------------------------------------------------------------
ReelType = Literal["explainer", "quiz", "flashcard", "myth_fact", "mnemonic"]


class ExplainerContent(BaseModel):
    hook: str
    points: list[str]
    takeaway: str
    emoji: str = "\U0001f4a1"


class QuizContent(BaseModel):
    """Public quiz card: the answer is checked server-side via POST /reels/{id}/answer."""

    question: str
    kind: Literal["multiple_choice", "true_false"]
    options: list[str]


class FlashcardContent(BaseModel):
    flashcard_id: UUID  # rate it with POST /flashcards/{id}/review (SM-2)
    front: str
    back: str


class MythFactContent(BaseModel):
    myth: str
    fact: str
    why: str


class MnemonicContent(BaseModel):
    mnemonic: str
    explanation: str


class BreakContent(BaseModel):
    title: str
    message: str
    reels_watched: int
    minutes: int
    concepts: list[str]


class ExplainerReel(BaseModel):
    type: Literal["explainer"]
    id: UUID
    concept: str
    content: ExplainerContent


class QuizReel(BaseModel):
    type: Literal["quiz"]
    id: UUID
    concept: str
    content: QuizContent


class FlashcardReel(BaseModel):
    type: Literal["flashcard"]
    id: UUID
    concept: str
    content: FlashcardContent


class MythFactReel(BaseModel):
    type: Literal["myth_fact"]
    id: UUID
    concept: str
    content: MythFactContent


class MnemonicReel(BaseModel):
    type: Literal["mnemonic"]
    id: UUID
    concept: str
    content: MnemonicContent


class BreakReel(BaseModel):
    """Synthetic wellbeing card (not stored, not tracked)."""

    type: Literal["break"]
    content: BreakContent


Reel = Annotated[
    ExplainerReel | QuizReel | FlashcardReel | MythFactReel | MnemonicReel | BreakReel,
    Field(discriminator="type"),
]


class ReelFeed(BaseModel):
    items: list[Reel]
    session_reels: int = Field(description="Reels viewed in the current session")
    break_every: int


class ReelViewSubmit(BaseModel):
    watch_ms: int = Field(ge=0, le=3_600_000)
    completed: bool = False


class ReelAnswerSubmit(BaseModel):
    response: str = Field(min_length=1, max_length=500)


class ReelAnswerResult(BaseModel):
    correct: bool
    correct_answer: str
    explanation: str


# Preferences & features -------------------------------------------------------
class Preferences(BaseModel):
    reels_enabled: bool


class PreferencesUpdate(BaseModel):
    reels_enabled: bool | None = None


class Features(BaseModel):
    reels: bool
