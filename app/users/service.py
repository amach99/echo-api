"""
app/users/service.py — User profile business logic.

get_user_profile:
    Look up any user by UUID. Raises 404 if not found.

update_user_profile:
    Apply non-null fields from UserUpdateRequest to the current user.
    Null values are treated as no-ops so clients can send partial updates
    without accidentally clearing existing data.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.users.schemas import UserUpdateRequest


async def get_user_profile(user_id: uuid.UUID, db: AsyncSession) -> User:
    """Fetch a user by ID. Raises HTTP 404 if not found."""
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "USER_NOT_FOUND", "message": "User not found."},
        )
    return user


async def update_user_profile(
    user: User,
    payload: UserUpdateRequest,
    db: AsyncSession,
) -> User:
    """
    Update the user's mutable profile fields.
    Only non-None fields in the payload are applied.
    Returns the updated User (caller's session commits).
    """
    if payload.bio is not None:
        user.bio = payload.bio
    if payload.profile_picture_url is not None:
        user.profile_picture_url = payload.profile_picture_url
    await db.flush()
    return user
