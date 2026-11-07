"""Reels agent: turns one concept into a set of short, swipeable study cards."""

from typing import Literal

from pydantic import BaseModel, Field

from app.llm import structured
from app.schemas import MnemonicContent, MythFactContent

SYSTEM = """You create TikTok/Reels-style micro-learning cards for university students,
using ONLY the numbered SOURCES. Each card must be readable in under 30 seconds.

Write for a phone screen: punchy, concrete, no filler, no "In this card...".
Use the same language as the sources.

Produce for the concept{concept_line}:
- explainer: `hook` is a scroll-stopping first line (max 12 words, a question or a
  surprising fact); exactly 3 `points` (max 20 words each); one-line `takeaway`; one `emoji`.
- quiz: one quick question. kind "multiple_choice" with 3-4 options, or "true_false" with
  options ["true", "false"]. `answer` copied exactly from options; one-sentence `explanation`.
- flashcard: short `front` (question/term) and `back` (precise answer).
- myth_fact: ONLY if students genuinely often get this wrong; otherwise null.
- mnemonic: ONLY if a good memory trick exists; otherwise null.
  Fill at most one of myth_fact / mnemonic.
- concept: the canonical concept name (short)."""


class ExplainerGen(BaseModel):
    hook: str
    points: list[str]
    takeaway: str
    emoji: str = "\U0001f4a1"


class QuizGen(BaseModel):
    question: str
    kind: Literal["multiple_choice", "true_false"]
    options: list[str]
    answer: str
    explanation: str


class FlashcardGen(BaseModel):
    front: str
    back: str


class ConceptReels(BaseModel):
    concept: str
    explainer: ExplainerGen
    quiz: QuizGen
    flashcard: FlashcardGen
    myth_fact: MythFactContent | None = Field(None)
    mnemonic: MnemonicContent | None = Field(None)


async def generate(concept: str | None, sources_text: str) -> ConceptReels:
    concept_line = f' "{concept}"' if concept else " that is most central in the sources"
    return await structured(ConceptReels).ainvoke(
        [
            ("system", SYSTEM.format(concept_line=concept_line)),
            ("human", f"SOURCES:\n{sources_text}"),
        ]
    )
