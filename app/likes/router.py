import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import get_current_user
from app.database import get_async_db
from app.likes.service import like_post, unlike_post
from app.middleware.age_verification import require_age_verified
from app.models.user import User

router = APIRouter(prefix="/likes", tags=["likes"],
                   dependencies=[Depends(require_age_verified)])


@router.post("/{post_id}", status_code=status.HTTP_201_CREATED)
async def like(post_id: uuid.UUID,
               current_user: User = Depends(get_current_user),
               db: AsyncSession = Depends(get_async_db)) -> dict:
    await like_post(current_user, post_id, db)
    return {"liked": True, "post_id": str(post_id)}


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlike(post_id: uuid.UUID,
                 current_user: User = Depends(get_current_user),
                 db: AsyncSession = Depends(get_async_db)) -> None:
    await unlike_post(current_user, post_id, db)
