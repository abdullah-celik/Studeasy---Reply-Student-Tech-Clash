from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from supabase import AsyncClient


async def recent(db: AsyncClient, user_id: str, course_id: str, limit: int) -> list[dict]:
    res = (
        await db.table("chat_messages")
        .select("id, role, content, created_at")
        .eq("user_id", user_id)
        .eq("course_id", course_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return list(reversed(res.data or []))


def to_langchain(rows: list[dict]) -> list[BaseMessage]:
    return [
        HumanMessage(r["content"]) if r["role"] == "user" else AIMessage(r["content"])
        for r in rows
    ]


async def save(db: AsyncClient, user_id: str, course_id: str, role: str, content: str) -> None:
    await (
        db.table("chat_messages")
        .insert({"user_id": user_id, "course_id": course_id, "role": role, "content": content})
        .execute()
    )
