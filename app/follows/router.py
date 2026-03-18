import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import get_current_user
from app.database import get_async_db
from app.follows.schemas import FollowCreate, FollowResponse
from app.follows.service import follow_user, unfollow_user
from app.middleware.age_verification import require_age_verified
from app.models.user import User

router = APIRouter(prefix="/follows", tags=["follows"],
                   dependencies=[Depends(require_age_verified)])


@router.post("", response_model=FollowResponse, status_code=status.HTTP_201_CREATED)
async def follow(payload: FollowCreate,
                 current_user: User = Depends(get_current_user),
                 db: AsyncSession = Depends(get_async_db)) -> FollowResponse:
    follow = await follow_user(current_user, payload.following_id, db)
    return FollowResponse(follower_id=follow.follower_id,
                          following_id=follow.following_id,
                          created_at=follow.created_at)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unfollow(user_id: uuid.UUID,
                   current_user: User = Depends(get_current_user),
                   db: AsyncSession = Depends(get_async_db)) -> None:
    await unfollow_user(current_user, user_id, db)
