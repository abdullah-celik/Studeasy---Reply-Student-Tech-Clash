from datetime import UTC, datetime

from fastapi import HTTPException, status
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from supabase import AsyncClient

TITLE_MAX = 60


async def recent(
    db: AsyncClient, user_id: str, course_id: str, limit: int, chat_id: str | None = None
) -> list[dict]:
    q = (
        db.table("chat_messages")
        .select("id, role, content, created_at")
        .eq("user_id", user_id)
        .eq("course_id", course_id)
    )
    if chat_id:
        q = q.eq("chat_id", chat_id)
    res = await q.order("created_at", desc=True).limit(limit).execute()
    return list(reversed(res.data or []))


def to_langchain(rows: list[dict]) -> list[BaseMessage]:
    return [
        HumanMessage(r["content"]) if r["role"] == "user" else AIMessage(r["content"])
        for r in rows
    ]


async def save(
    db: AsyncClient,
    user_id: str,
    course_id: str,
    role: str,
    content: str,
    chat_id: str | None = None,
) -> None:
    row = {"user_id": user_id, "course_id": course_id, "role": role, "content": content}
    if chat_id:
        row["chat_id"] = chat_id
    await db.table("chat_messages").insert(row).execute()


# Threads ---------------------------------------------------------------------
def title_from(message: str) -> str:
    """First line of the first message, trimmed to a sidebar-friendly length."""
    line = " ".join(message.strip().split())
    return line if len(line) <= TITLE_MAX else line[: TITLE_MAX - 1].rstrip() + "…"


async def list_threads(db: AsyncClient, user_id: str, course_id: str) -> list[dict]:
    res = (
        await db.table("chats")
        .select("id, title, created_at, updated_at")
        .eq("user_id", user_id)
        .eq("course_id", course_id)
        .order("updated_at", desc=True)
        .execute()
    )
    return res.data or []


async def create_thread(db: AsyncClient, user_id: str, course_id: str, title: str | None) -> dict:
    res = await (
        db.table("chats")
        .insert({"user_id": user_id, "course_id": course_id, "title": title})
        .execute()
    )
    return res.data[0]


async def owned_thread(db: AsyncClient, user_id: str, chat_id: str, course_id: str | None = None) -> dict:
    q = db.table("chats").select("*").eq("id", chat_id).eq("user_id", user_id)
    if course_id:
        q = q.eq("course_id", course_id)
    res = await q.limit(1).execute()
    if not res.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chat not found")
    return res.data[0]


async def touch_thread(db: AsyncClient, thread: dict, first_message: str) -> None:
    """Bump updated_at (sidebar order) and name untitled threads after their first message."""
    changes: dict = {"updated_at": datetime.now(UTC).isoformat()}
    if not thread.get("title"):
        changes["title"] = title_from(first_message)
    await db.table("chats").update(changes).eq("id", thread["id"]).execute()


async def rename_thread(db: AsyncClient, user_id: str, chat_id: str, title: str) -> dict:
    await owned_thread(db, user_id, chat_id)
    res = await db.table("chats").update({"title": title}).eq("id", chat_id).execute()
    return res.data[0]


async def delete_thread(db: AsyncClient, user_id: str, chat_id: str) -> None:
    await db.table("chats").delete().eq("id", chat_id).eq("user_id", user_id).execute()
