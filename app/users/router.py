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

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_async_db
from app.models.post import Post
from app.models.user import User
from app.posts.schemas import PostResponse
from app.users.schemas import UserPublicResponse, UserUpdateRequest
from app.follows.service import get_followers, get_following
from app.users.service import get_user_profile, get_user_posts, search_users, update_user_profile

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
# /search — username search (public)
# ------------------------------------------------------------------ #


@router.get(
    "/search",
    response_model=list[UserPublicResponse],
    summary="Search users by username",
)
async def search_users_endpoint(
    q: str = Query(..., min_length=1, max_length=30, description="Username search term"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_async_db),
) -> list[User]:
    """Case-insensitive username search. Public — no auth required."""
    return await search_users(q, db, skip=skip, limit=limit)


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


@router.get(
    "/{user_id}/posts",
    response_model=list[PostResponse],
    summary="Get a user's posts",
)
async def get_user_posts_endpoint(
    user_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_async_db),
) -> list[Post]:
    """Returns a user's posts newest-first. Public — no auth required."""
    return await get_user_posts(user_id, db, skip=skip, limit=limit)


@router.get(
    "/{user_id}/followers",
    response_model=list[UserPublicResponse],
    summary="Get a user's followers",
)
async def get_user_followers(
    user_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_async_db),
) -> list[User]:
    """Returns users who follow user_id. Public — no auth required."""
    return await get_followers(user_id, db, skip=skip, limit=limit)


@router.get(
    "/{user_id}/following",
    response_model=list[UserPublicResponse],
    summary="Get users that a user follows",
)
async def get_user_following(
    user_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_async_db),
) -> list[User]:
    """Returns users that user_id follows. Public — no auth required."""
    return await get_following(user_id, db, skip=skip, limit=limit)
