import uuid
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.post import Post
from app.models.user import User
from app.models.vote import Vote


async def cast_vote(user: User, post_id: uuid.UUID, vote_value: int, db: AsyncSession) -> Vote:
    result = await db.execute(select(Post).where(Post.post_id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"code": "POST_NOT_FOUND"})
    if not post.is_pulse_post:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail={"code": "CANNOT_VOTE_LIFE_POST",
                                    "message": "Use likes for Life posts."})

    result = await db.execute(select(Vote).where(
        Vote.user_id == user.user_id, Vote.post_id == post_id))
    existing = result.scalar_one_or_none()

    delta = vote_value
    if existing:
        delta = vote_value - existing.vote_value   # net change for reputation
        existing.vote_value = vote_value
        vote = existing
    else:
        vote = Vote(user_id=user.user_id, post_id=post_id, vote_value=vote_value)
        db.add(vote)

    # Atomically update the author's internal reputation score
    await db.execute(
        update(User)
        .where(User.user_id == post.author_id)
        .values(reputation_score=User.reputation_score + delta)
    )
    await db.flush()
    return vote


async def remove_vote(user: User, post_id: uuid.UUID, db: AsyncSession) -> None:
    result = await db.execute(select(Vote).where(
        Vote.user_id == user.user_id, Vote.post_id == post_id))
    vote = result.scalar_one_or_none()
    if not vote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"code": "VOTE_NOT_FOUND"})
    # Reverse reputation impact
    post_result = await db.execute(select(Post).where(Post.post_id == post_id))
    post = post_result.scalar_one_or_none()
    if post:
        await db.execute(
            update(User)
            .where(User.user_id == post.author_id)
            .values(reputation_score=User.reputation_score - vote.vote_value)
        )
    await db.delete(vote)
