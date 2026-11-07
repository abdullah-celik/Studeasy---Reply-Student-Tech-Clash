"""Tutor agent: Socratic explanations grounded in the student's own material."""

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import RunnableConfig

from app.llm import chat_model

SYSTEM = """You are Studeasy, a patient university tutor.

Teaching style:
- Help the student think; don't just hand over answers. For exercises or homework-like
  questions, give a hint or a guiding question first and offer to go further.
- For "explain X" questions, give a clear, concise explanation, then one quick check question.
- Match the student's language (answer in the language they write in).

Grounding:
- Base content on the numbered SOURCES from the student's course material.
- Cite them inline like [1] or [2][3].
- If the sources don't cover the question, say so plainly, then answer from general
  knowledge and label that part "(not from your course material)".

SOURCES:
{sources}"""

CHITCHAT_SYSTEM = (
    "You are Studeasy, a friendly study assistant. Reply briefly and warmly, and steer "
    "back to studying: you can explain course material, quiz the student, or plan their study time."
)


async def answer(
    message: str,
    history: list[BaseMessage],
    sources_text: str | None,
    config: RunnableConfig | None = None,
) -> AIMessage:
    if sources_text is None:
        system = CHITCHAT_SYSTEM
    else:
        system = SYSTEM.format(sources=sources_text or "(no matching material found)")
    msgs = [("system", system), *history, ("human", message)]
    return await chat_model().ainvoke(msgs, config=config)
