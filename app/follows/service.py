import uuid
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.follow import Follow
from app.models.user import User


async def follow_user(follower: User, following_id: uuid.UUID, db: AsyncSession) -> Follow:
    if follower.user_id == following_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail={"code": "CANNOT_FOLLOW_SELF"})
    result = await db.execute(select(User).where(User.user_id == following_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"code": "USER_NOT_FOUND"})
    existing = await db.execute(select(Follow).where(
        Follow.follower_id == follower.user_id, Follow.following_id == following_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail={"code": "ALREADY_FOLLOWING"})
    follow = Follow(follower_id=follower.user_id, following_id=following_id)
    db.add(follow)
    await db.flush()
    return follow


async def get_followers(user_id: uuid.UUID, db: AsyncSession, skip: int = 0, limit: int = 20) -> list[User]:
    """Return users who follow user_id."""
    result = await db.execute(
        select(User)
        .join(Follow, Follow.follower_id == User.user_id)
        .where(Follow.following_id == user_id)
        .order_by(Follow.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_following(user_id: uuid.UUID, db: AsyncSession, skip: int = 0, limit: int = 20) -> list[User]:
    """Return users that user_id follows."""
    result = await db.execute(
        select(User)
        .join(Follow, Follow.following_id == User.user_id)
        .where(Follow.follower_id == user_id)
        .order_by(Follow.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def unfollow_user(follower: User, following_id: uuid.UUID, db: AsyncSession) -> None:
    result = await db.execute(select(Follow).where(
        Follow.follower_id == follower.user_id, Follow.following_id == following_id))
    follow = result.scalar_one_or_none()
    if not follow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"code": "FOLLOW_NOT_FOUND"})
    await db.delete(follow)
