"""Quiz master agent: writes questions and flashcards, grades open answers."""

from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, Field

from app.agents.lenient import LIntList, LStr, LStrList
from app.llm import structured
from app.schemas import QuestionType

QUESTION_SYSTEM = """You write exam-style practice questions from numbered SOURCES only.
Rules:
- Produce exactly {count} questions using only these types: {types}. Mix them.
- multiple_choice: 4 plausible options; `answer` must be copied exactly from `options`.
- true_false: options must be ["true", "false"]; answer is "true" or "false".
- open: a short-answer question; `answer` is a model answer of 1-3 sentences.
- `concept`: the key concept tested, as a short canonical name{concept_hint}.
- `source_indices`: the [n] numbers of the sources the question is based on.
- Write in the same language as the sources.{topic_line}"""

FLASHCARD_SYSTEM = """You create concise flashcards from numbered SOURCES only.
Produce exactly {count} cards. Front: a question or term. Back: a short, precise answer.
`concept`: the key concept, short canonical name{concept_hint}. Same language as the sources.{topic_line}"""

GRADE_SYSTEM = """You grade a student's short answer.
Compare it with the model answer and the source material. Give a score from 0 to 1
(partial credit allowed) and 1-3 sentences of encouraging, specific feedback that
says what was right and what was missing. Ignore spelling mistakes."""


def _to_question_type(v: Any) -> Any:
    if not isinstance(v, str):
        return v
    key = v.strip().lower().replace("-", " ").replace("_", " ").replace("/", " ")
    aliases = {
        "multiple choice": "multiple_choice", "mcq": "multiple_choice", "mc": "multiple_choice",
        "true false": "true_false", "truefalse": "true_false", "tf": "true_false",
        "boolean": "true_false", "open": "open", "open ended": "open", "short answer": "open",
    }
    return aliases.get(key, v)


class GeneratedQuestion(BaseModel):
    type: Annotated[QuestionType, BeforeValidator(_to_question_type)]
    prompt: LStr
    options: LStrList = Field(default_factory=list)
    answer: LStr
    explanation: LStr = ""
    concept: LStr
    source_indices: LIntList = Field(default_factory=list)


class GeneratedQuiz(BaseModel):
    questions: list[GeneratedQuestion]


class GeneratedFlashcard(BaseModel):
    front: LStr
    back: LStr
    concept: LStr


class GeneratedDeck(BaseModel):
    cards: list[GeneratedFlashcard]


class Grade(BaseModel):
    score: float = Field(ge=0, le=1)
    feedback: str


def _hints(topic: str | None, known_concepts: list[str]) -> tuple[str, str]:
    concept_hint = (
        f"; reuse one of these when it fits: {', '.join(known_concepts[:30])}"
        if known_concepts
        else ""
    )
    topic_line = f"\nFocus on: {topic}" if topic else ""
    return concept_hint, topic_line


async def generate_questions(
    sources_text: str,
    types: list[QuestionType],
    count: int,
    topic: str | None = None,
    known_concepts: list[str] | None = None,
) -> GeneratedQuiz:
    concept_hint, topic_line = _hints(topic, known_concepts or [])
    system = QUESTION_SYSTEM.format(
        count=count, types=", ".join(types), concept_hint=concept_hint, topic_line=topic_line
    )
    return await structured(GeneratedQuiz).ainvoke(
        [("system", system), ("human", f"SOURCES:\n{sources_text}")]
    )


async def generate_flashcards(
    sources_text: str,
    count: int,
    topic: str | None = None,
    known_concepts: list[str] | None = None,
) -> GeneratedDeck:
    concept_hint, topic_line = _hints(topic, known_concepts or [])
    system = FLASHCARD_SYSTEM.format(count=count, concept_hint=concept_hint, topic_line=topic_line)
    return await structured(GeneratedDeck).ainvoke(
        [("system", system), ("human", f"SOURCES:\n{sources_text}")]
    )


async def grade_open_answer(
    question: str, model_answer: str, response: str, sources_text: str
) -> Grade:
    human = (
        f"QUESTION:\n{question}\n\nMODEL ANSWER:\n{model_answer}\n\n"
        f"SOURCE MATERIAL:\n{sources_text or '(none)'}\n\nSTUDENT ANSWER:\n{response}"
    )
    return await structured(Grade).ainvoke([("system", GRADE_SYSTEM), ("human", human)])
