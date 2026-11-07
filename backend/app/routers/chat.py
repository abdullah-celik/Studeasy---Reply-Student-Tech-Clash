"""Chat endpoint: runs the multi-agent graph and streams events over SSE.

Event types (see docs/FRONTEND.md for the TypeScript union):
  intent, sources, token, verification, quiz, plan, error, done
"""

import json
import logging

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.agents.graph import build_graph
from app.config import get_settings
from app.db import get_db
from app.deps import CurrentUser, get_current_user, get_owned_course
from app.schemas import ChatMessage, ChatRequest
from app.services import chat_history
from supabase import AsyncClient

log = logging.getLogger(__name__)
router = APIRouter(prefix="/courses/{course_id}/chat", tags=["chat"])


def _event(name: str, data: dict) -> dict:
    return {"event": name, "data": json.dumps(data, default=str)}


@router.post(
    "",
    summary="Send a message to the agents (Server-Sent Events stream)",
    response_class=EventSourceResponse,
)
async def chat(
    body: ChatRequest,
    course: dict = Depends(get_owned_course),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    course_id = course["id"]
    rows = await chat_history.recent(db, user.id, course_id, get_settings().chat_history_limit)
    await chat_history.save(db, user.id, course_id, "user", body.message)

    state = {
        "user_id": user.id,
        "course_id": course_id,
        "message": body.message,
        "history": chat_history.to_langchain(rows),
    }

    async def events():
        answer_parts: list[str] = []
        stored_reply = ""
        try:
            async for mode, chunk in build_graph().astream(
                state,
                config={"configurable": {"db": db}},
                stream_mode=["messages", "updates"],
            ):
                if mode == "messages":
                    msg, meta = chunk
                    # Only the tutor's tokens are user-facing; other agents emit structured data.
                    if meta.get("langgraph_node") == "tutor" and isinstance(msg.content, str) and msg.content:
                        answer_parts.append(msg.content)
                        yield _event("token", {"text": msg.content})
                    continue

                for node, update in (chunk or {}).items():
                    if not update:
                        continue
                    if node == "orchestrator":
                        yield _event("intent", {"intent": update["intent"], "topic": update.get("topic")})
                    elif node == "retrieve":
                        yield _event("sources", {"sources": update["sources"]})
                    elif node == "verifier":
                        yield _event("verification", update["verification"])
                    elif "error" in update:
                        stored_reply = update["error"]
                        yield _event("error", {"message": update["error"]})
                    elif node == "quiz_master":
                        stored_reply = f"[Generated a quiz with {len(update['quiz']['questions'])} questions]"
                        yield _event("quiz", update["quiz"])
                    elif node == "planner":
                        stored_reply = f"[Study plan] {update['plan']['summary']}"
                        yield _event("plan", update["plan"])

            reply = "".join(answer_parts) or stored_reply
            if reply:
                await chat_history.save(db, user.id, course_id, "assistant", reply)
            yield _event("done", {})
        except Exception:
            log.exception("Chat run failed")
            yield _event("error", {"message": "Something went wrong. Please try again."})

    return EventSourceResponse(events())


@router.get("/history", response_model=list[ChatMessage])
async def history(
    limit: int = 50,
    course: dict = Depends(get_owned_course),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    return await chat_history.recent(db, user.id, course["id"], min(limit, 200))
