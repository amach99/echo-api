"""app/likes/router.py — Like/unlike endpoints."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_async_db
from app.likes.service import like_post, unlike_post
from app.middleware.age_verification import require_age_verified
from app.models.user import User
from app.notifications.adapter import PushAdapter, get_push_adapter
from app.notifications.service import dispatch_push, get_tokens_for_post_author

router = APIRouter(
    prefix="/likes",
    tags=["likes"],
    dependencies=[Depends(require_age_verified)],
)


@router.post("/{post_id}", status_code=status.HTTP_201_CREATED)
async def like(
    post_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
    push_adapter: PushAdapter = Depends(get_push_adapter),
) -> dict:
    await like_post(current_user, post_id, db)

    # Notify the post author — look up tokens while DB session is open
    tokens = await get_tokens_for_post_author(post_id=post_id, db=db)
    if tokens:
        background_tasks.add_task(
            dispatch_push,
            adapter=push_adapter,
            device_tokens=tokens,
            title="New like",
            body=f"@{current_user.username} liked your post",
            data={"type": "like", "post_id": str(post_id)},
        )

    return {"liked": True, "post_id": str(post_id)}


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlike(
    post_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> None:
    await unlike_post(current_user, post_id, db)
