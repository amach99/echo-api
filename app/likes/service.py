import uuid
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.like import Like
from app.models.post import Post
from app.models.user import User


async def like_post(user: User, post_id: uuid.UUID, db: AsyncSession) -> Like:
    result = await db.execute(select(Post).where(Post.post_id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"code": "POST_NOT_FOUND"})
    if post.is_pulse_post:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail={"code": "CANNOT_LIKE_PULSE_POST",
                                    "message": "Use upvote/downvote for Pulse posts."})
    existing = await db.execute(select(Like).where(
        Like.user_id == user.user_id, Like.post_id == post_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail={"code": "ALREADY_LIKED"})
    like = Like(user_id=user.user_id, post_id=post_id)
    db.add(like)
    await db.flush()
    return like


async def unlike_post(user: User, post_id: uuid.UUID, db: AsyncSession) -> None:
    result = await db.execute(select(Like).where(
        Like.user_id == user.user_id, Like.post_id == post_id))
    like = result.scalar_one_or_none()
    if not like:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"code": "LIKE_NOT_FOUND"})
    await db.delete(like)
