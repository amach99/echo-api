"""
app/posts/service.py — Post creation business logic.

Feed routing is determined server-side from the author's account_type.
Clients CANNOT influence is_pulse_post.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.post import Post
from app.models.user import User
from app.posts.schemas import PostCreate


async def create_post(
    payload: PostCreate,
    author: User,
    db: AsyncSession,
) -> Post:
    """
    Create a new post. Feed routing is automatic:
      Human account    → is_pulse_post = False (Life Feed)
      Business/Meme/Info → is_pulse_post = True  (Pulse Feed)
    """
    is_pulse = author.is_pulse_account  # property on User model

    post = Post(
        author_id=author.user_id,
        content_text=payload.content_text,
        media_url=payload.media_url,
        is_pulse_post=is_pulse,
    )
    db.add(post)
    await db.flush()
    return post


async def get_post_by_id(post_id: uuid.UUID, db: AsyncSession) -> Post | None:
    result = await db.execute(
        select(Post).where(Post.post_id == post_id)
    )
    return result.scalar_one_or_none()
