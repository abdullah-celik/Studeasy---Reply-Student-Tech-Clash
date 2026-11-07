from typing import TypedDict

from langchain_core.messages import BaseMessage


class ChatState(TypedDict, total=False):
    # input
    user_id: str
    course_id: str
    message: str
    history: list[BaseMessage]
    # orchestrator
    intent: str
    topic: str | None
    # retrieval / tutor / verifier
    sources: list[dict]
    sources_text: str
    answer: str
    verification: dict
    # quiz master / planner
    quiz: dict
    plan: dict
    error: str
