from fastapi import APIRouter, Depends

from app.config import get_settings
from app.db import get_db
from app.deps import CurrentUser, get_current_user
from app.schemas import Features, Preferences, PreferencesUpdate
from app.services import reels
from supabase import AsyncClient

router = APIRouter(tags=["me"])


@router.get("/features", response_model=Features)
async def features():
    """Which optional modules this deployment has. No auth: the frontend reads it at startup."""
    return {"reels": get_settings().enable_reels}


@router.get("/me/preferences", response_model=Preferences)
async def get_preferences(
    user: CurrentUser = Depends(get_current_user), db: AsyncClient = Depends(get_db)
):
    return await reels.get_preferences(db, user.id)


@router.patch("/me/preferences", response_model=Preferences)
async def update_preferences(
    body: PreferencesUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    return await reels.update_preferences(db, user.id, body.model_dump(exclude_none=True))
