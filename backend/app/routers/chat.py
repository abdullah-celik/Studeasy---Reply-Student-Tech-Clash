"""Chat endpoint: runs the multi-agent graph and streams events over SSE.

Event types (see docs/FRONTEND.md for the TypeScript union):
  intent, sources, token, verification, quiz, plan, error, done
"""

import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sse_starlette.sse import EventSourceResponse

from app.agents.graph import build_graph
from app.config import get_settings
from app.db import get_db
from app.deps import CurrentUser, get_current_user, get_owned_course
from app.schemas import ChatMessage, ChatRequest, ChatThread, ChatThreadCreate, ChatThreadUpdate
from app.services import chat_history, planning
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
    chat_id = str(body.chat_id) if body.chat_id else None
    if chat_id:
        thread = await chat_history.owned_thread(db, user.id, chat_id, course_id)
        await chat_history.touch_thread(db, thread, body.message)
    rows = await chat_history.recent(
        db, user.id, course_id, get_settings().chat_history_limit, chat_id
    )
    await chat_history.save(db, user.id, course_id, "user", body.message, chat_id)

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
                        try:  # keep chat-made plans in the Plans history too
                            await planning.save_plan(db, user.id, course_id, update["plan"])
                        except Exception:
                            log.exception("Could not save chat plan")
                        yield _event("plan", update["plan"])

            reply = "".join(answer_parts) or stored_reply
            if reply:
                await chat_history.save(db, user.id, course_id, "assistant", reply, chat_id)
            yield _event("done", {})
        except Exception:
            log.exception("Chat run failed")
            yield _event("error", {"message": "Something went wrong. Please try again."})

    return EventSourceResponse(events())


@router.get("/history", response_model=list[ChatMessage])
async def history(
    limit: int = 50,
    chat_id: UUID | None = None,
    course: dict = Depends(get_owned_course),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Messages of one thread (`chat_id`), or of the whole course when omitted."""
    return await chat_history.recent(
        db, user.id, course["id"], min(limit, 200), str(chat_id) if chat_id else None
    )


# Threads: several chats per course -----------------------------------------------
threads = APIRouter(tags=["chat"])


@threads.get("/courses/{course_id}/chats", response_model=list[ChatThread])
async def list_chats(
    course: dict = Depends(get_owned_course),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Newest activity first. Untitled chats get their first message as title."""
    return await chat_history.list_threads(db, user.id, course["id"])


@threads.post(
    "/courses/{course_id}/chats", response_model=ChatThread, status_code=status.HTTP_201_CREATED
)
async def create_chat(
    body: ChatThreadCreate,
    course: dict = Depends(get_owned_course),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    return await chat_history.create_thread(db, user.id, course["id"], body.title)


@threads.patch("/chats/{chat_id}", response_model=ChatThread)
async def rename_chat(
    chat_id: UUID,
    body: ChatThreadUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    return await chat_history.rename_thread(db, user.id, str(chat_id), body.title)


@threads.delete("/chats/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    chat_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    await chat_history.delete_thread(db, user.id, str(chat_id))
