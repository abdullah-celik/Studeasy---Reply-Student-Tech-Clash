"""Optional reels module. Mounted only when ENABLE_REELS=true; each student must also
opt in via PATCH /api/me/preferences {"reels_enabled": true}."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import get_settings
from app.db import get_db
from app.deps import CurrentUser, get_current_user, get_owned_course
from app.schemas import ReelAnswerResult, ReelAnswerSubmit, ReelFeed, ReelViewSubmit
from app.services import reels
from supabase import AsyncClient


async def reels_enabled_for_user(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
) -> CurrentUser:
    prefs = await reels.get_preferences(db, user.id)
    if not prefs["reels_enabled"]:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Reels are turned off in your settings"
        )
    return user


router = APIRouter(tags=["reels"])


@router.get("/courses/{course_id}/reels/feed", response_model=ReelFeed)
async def feed(
    limit: int | None = Query(None, ge=1, le=20),
    course: dict = Depends(get_owned_course),
    user: CurrentUser = Depends(reels_enabled_for_user),
    db: AsyncClient = Depends(get_db),
):
    """Next page of unseen reels. Call again when ~2 are left; new ones are generated on demand."""
    return await reels.get_feed(
        db, user.id, course["id"], limit or get_settings().reels_page_size
    )


@router.post("/reels/{reel_id}/view", status_code=status.HTTP_204_NO_CONTENT)
async def view(
    reel_id: UUID,
    body: ReelViewSubmit,
    user: CurrentUser = Depends(reels_enabled_for_user),
    db: AsyncClient = Depends(get_db),
):
    """Send when the student swipes away: marks the reel seen and records watch time."""
    await reels.record_view(db, user.id, str(reel_id), body.watch_ms, body.completed)


@router.post("/reels/{reel_id}/answer", response_model=ReelAnswerResult)
async def answer(
    reel_id: UUID,
    body: ReelAnswerSubmit,
    user: CurrentUser = Depends(reels_enabled_for_user),
    db: AsyncClient = Depends(get_db),
):
    return await reels.answer_quiz(db, user.id, str(reel_id), body.response)
