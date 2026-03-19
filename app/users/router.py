"""
app/users/router.py — User profile endpoints.

Route registration order is intentional:
  /me routes are registered BEFORE /{user_id} so that the literal string
  "me" is not mistakenly matched as a UUID parameter.

GET  /users/me         requires auth — returns current user's profile
PATCH /users/me        requires auth — updates bio / profile_picture_url
GET  /users/{user_id}  public — returns any user's public profile
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_async_db
from app.models.user import User
from app.users.schemas import UserPublicResponse, UserUpdateRequest
from app.users.service import get_user_profile, update_user_profile

router = APIRouter(prefix="/users", tags=["users"])


# ------------------------------------------------------------------ #
# /me routes — MUST come before /{user_id} to avoid path collision
# ------------------------------------------------------------------ #


@router.get(
    "/me",
    response_model=UserPublicResponse,
    summary="Get the current user's profile",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> User:
    """Returns the authenticated user's own profile."""
    return current_user


@router.patch(
    "/me",
    response_model=UserPublicResponse,
    summary="Update the current user's profile",
)
async def update_me(
    payload: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> User:
    """
    Update bio and/or profile_picture_url for the authenticated user.
    Null values are ignored (existing data preserved).
    """
    return await update_user_profile(current_user, payload, db)


# ------------------------------------------------------------------ #
# /{user_id} — public profile lookup
# ------------------------------------------------------------------ #


@router.get(
    "/{user_id}",
    response_model=UserPublicResponse,
    summary="Get a user's public profile",
)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
) -> User:
    """Returns the public profile for any user. No authentication required."""
    return await get_user_profile(user_id, db)
