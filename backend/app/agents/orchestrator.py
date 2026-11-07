"""Orchestrator: classifies what the student wants and picks the specialist agent."""

from typing import Literal

from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from app.llm import structured

Intent = Literal["explain", "quiz", "plan", "chitchat"]

SYSTEM = """You route messages in a study assistant. Choose one intent:
- explain: the student asks about course content, wants an explanation, or is stuck on a problem.
- quiz: the student wants to be tested / practice questions.
- plan: the student asks what or when to study, mentions exams or schedules.
- chitchat: greetings, thanks, or anything unrelated to studying.
Also extract the topic the student mentions, if any (short phrase), else null."""


class Route(BaseModel):
    intent: Intent
    topic: str | None = Field(None, description="Topic mentioned by the student, if any")


async def route(
    message: str, history: list[BaseMessage], config: RunnableConfig | None = None
) -> Route:
    msgs = [("system", SYSTEM), *history[-4:], ("human", message)]
    return await structured(Route).ainvoke(msgs, config=config)
