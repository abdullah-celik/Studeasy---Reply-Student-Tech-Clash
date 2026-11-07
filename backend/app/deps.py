from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db import get_db
from supabase import AsyncClient

bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    id: str
    email: str | None


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncClient = Depends(get_db),
) -> CurrentUser:
    """Verify the Supabase access token sent by the frontend (Authorization: Bearer <jwt>).

    Asking Supabase Auth to resolve the token works for both legacy (HS256) and
    asymmetric signing keys. It costs one HTTP call per request, which is fine for a demo;
    swap for local JWKS verification if latency matters.
    """
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        res = await db.auth.get_user(creds.credentials)
    except Exception as exc:  # invalid / expired token
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from exc
    if res is None or res.user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    return CurrentUser(id=res.user.id, email=res.user.email)


async def get_owned_course(
    course_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
) -> dict:
    """Load a course and make sure it belongs to the caller (404 otherwise)."""
    res = (
        await db.table("courses")
        .select("*")
        .eq("id", str(course_id))
        .eq("user_id", user.id)
        .limit(1)
        .execute()
    )
    if not res.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    return res.data[0]
