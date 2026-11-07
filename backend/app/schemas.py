"""Request/response models.

These are the API contract with the TypeScript frontend: FastAPI turns them into
/openapi.json, from which the frontend generates its types (see docs/FRONTEND.md).
"""

from datetime import date, datetime
from typing import Literal
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
    front: str
    back: str
    concept: str
    ease: float
    interval: int
    repetitions: int
    due_at: datetime


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
