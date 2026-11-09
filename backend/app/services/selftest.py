"""A small AI check at startup, reported in /api/health.

It tries what the app relies on: routing (a forced tool call), a two-question quiz
(the most complex schema) and a streamed answer, plus one embedding. It costs a few
thousand tokens per start, and makes provider problems visible without signing in.
"""

import logging
import time

from app.agents.orchestrator import Route
from app.agents.quiz import GeneratedQuiz, generate_questions
from app.config import get_settings
from app.llm import chat_model, embeddings, structured

log = logging.getLogger(__name__)

STATUS: dict = {"state": "not run"}

SAMPLE = (
    "[1] (biology.pdf, page 2)\nPhotosynthesis turns light energy into chemical energy. "
    "It happens in the chloroplasts of plant cells, which contain the green pigment "
    "chlorophyll. The light-dependent reactions take place in the thylakoid membranes and "
    "produce ATP, NADPH and oxygen; the Calvin cycle in the stroma uses them to fix CO2 into sugar."
)


def _clean(text: str) -> str:
    account = get_settings().cloudflare_account_id
    if account:
        text = text.replace(account, "<account>")
    return text[:240]


async def _timed(fn) -> str:
    start = time.perf_counter()
    try:
        detail = await fn()
        return f"ok in {time.perf_counter() - start:.1f}s{f' ({detail})' if detail else ''}"
    except Exception as exc:  # report, never crash startup
        log.warning("AI self-test step failed: %s", exc)
        return f"failed: {type(exc).__name__}: {_clean(str(exc))}"


async def _check_model(model: str) -> dict:
    async def route():
        r = await structured(Route, model).ainvoke(
            [
                ("system", "Classify the student's message."),
                ("human", "Explain photosynthesis to me"),
            ]
        )
        return f"intent={r.intent}, topic={r.topic}"

    async def quiz():
        if model == get_settings().chat_model_name:
            q = await generate_questions(SAMPLE, ["multiple_choice", "true_false"], 2)
        else:
            q = await structured(GeneratedQuiz, model).ainvoke(
                [
                    (
                        "system",
                        "Write 2 practice questions (multiple_choice, true_false) from SOURCES.",
                    ),
                    ("human", f"SOURCES:\n{SAMPLE}"),
                ]
            )
        return f"{len(q.questions)} questions"

    async def stream():
        parts = []
        async for chunk in chat_model(model).astream(
            [
                ("system", "Answer in one short sentence."),
                ("human", "Where does photosynthesis happen?"),
            ]
        ):
            parts.append(chunk.content if isinstance(chunk.content, str) else "")
        text = "".join(parts).strip()
        if not text:
            raise ValueError("empty answer")
        if "<think>" in text:
            raise ValueError(f"answer contains reasoning text: {text[:80]}")
        return f"{len(parts)} chunks: {text[:80]}"

    return {
        "route": await _timed(route),
        "quiz": await _timed(quiz),
        "stream": await _timed(stream),
    }


async def run_self_test() -> None:
    s = get_settings()
    STATUS.clear()
    STATUS.update(state="running", provider=s.llm_provider)

    async def embed():
        vector = await embeddings().aembed_query("photosynthesis")
        if len(vector) != s.vector_size:
            raise ValueError(f"got {len(vector)} dimensions, the database expects {s.vector_size}")
        return f"{len(vector)} dimensions"

    STATUS["embeddings"] = await _timed(embed)
    models = [
        s.chat_model_name,
        *[m for m in s.ai_self_test_extra_models if m != s.chat_model_name],
    ]
    STATUS["models"] = {m: await _check_model(m) for m in models}
    STATUS["state"] = "done"
    log.info("AI self-test: %s", STATUS)
