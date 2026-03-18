"""
app/posts/router.py — Post creation and retrieval endpoints.

Write actions are gated by require_age_verified (Rule 2).
Rate limiting applied at post creation (Rule 6 + PRD §4).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_async_db
from app.middleware.age_verification import require_age_verified
from app.middleware.rate_limiter import post_rate_limit
from app.models.user import User
from app.posts.schemas import PostCreate, PostResponse
from app.posts.service import create_post, get_post_by_id

router = APIRouter(prefix="/posts", tags=["posts"])


@router.post(
    "",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_age_verified), Depends(post_rate_limit())],
)
async def create_new_post(
    payload: PostCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> PostResponse:
    """
    Create a post. Feed routing (Life vs Pulse) is automatic based on account_type.
    Requires: 18+ ID verified.  Rate limits: 5/hr (Human), 2/hr (Business/Meme/Info).
    """
    post = await create_post(payload, current_user, db)
    return PostResponse(
        post_id=post.post_id,
        author_id=post.author_id,
        author_username=current_user.username,
        content_text=post.content_text,
        media_url=post.media_url,
        is_pulse_post=post.is_pulse_post,
        created_at=post.created_at,
    )


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
) -> PostResponse:
    """Fetch a single post by ID. Public read — no auth required."""
    post = await get_post_by_id(post_id, db)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "POST_NOT_FOUND", "message": "Post not found."},
        )
    return PostResponse(
        post_id=post.post_id,
        author_id=post.author_id,
        author_username=post.author.username,
        content_text=post.content_text,
        media_url=post.media_url,
        is_pulse_post=post.is_pulse_post,
        created_at=post.created_at,
    )
