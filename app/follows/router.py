"""app/follows/router.py — Follow/unfollow endpoints."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_async_db
from app.follows.schemas import FollowCreate, FollowResponse
from app.follows.service import follow_user, unfollow_user
from app.middleware.age_verification import require_age_verified
from app.models.user import User
from app.notifications.adapter import PushAdapter, get_push_adapter
from app.notifications.service import dispatch_push, get_tokens_for_user

router = APIRouter(
    prefix="/follows",
    tags=["follows"],
    dependencies=[Depends(require_age_verified)],
)


@router.post("", response_model=FollowResponse, status_code=status.HTTP_201_CREATED)
async def follow(
    payload: FollowCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
    push_adapter: PushAdapter = Depends(get_push_adapter),
) -> FollowResponse:
    follow_obj = await follow_user(current_user, payload.following_id, db)

    # Notify the followed user — look up tokens while DB session is open
    tokens = await get_tokens_for_user(user_id=payload.following_id, db=db)
    if tokens:
        background_tasks.add_task(
            dispatch_push,
            adapter=push_adapter,
            device_tokens=tokens,
            title="New follower",
            body=f"@{current_user.username} started following you",
            data={"type": "follow", "user_id": str(current_user.user_id)},
        )

    return FollowResponse(
        follower_id=follow_obj.follower_id,
        following_id=follow_obj.following_id,
        created_at=follow_obj.created_at,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unfollow(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> None:
    await unfollow_user(current_user, user_id, db)
