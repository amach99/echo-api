import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import get_current_user
from app.database import get_async_db
from app.middleware.age_verification import require_age_verified
from app.models.user import User
from app.mute_echoes.service import list_muted, mute_echoes, unmute_echoes

router = APIRouter(prefix="/mute-echoes", tags=["mute-echoes"],
                   dependencies=[Depends(require_age_verified)])


@router.post("/{user_id}", status_code=status.HTTP_201_CREATED)
async def mute(user_id: uuid.UUID,
               current_user: User = Depends(get_current_user),
               db: AsyncSession = Depends(get_async_db)) -> dict:
    """Mute a user's Echoes — their reposts will no longer appear in your Life Feed."""
    await mute_echoes(current_user, user_id, db)
    return {"muted_user_id": str(user_id), "muted": True}


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unmute(user_id: uuid.UUID,
                 current_user: User = Depends(get_current_user),
                 db: AsyncSession = Depends(get_async_db)) -> None:
    await unmute_echoes(current_user, user_id, db)


@router.get("", status_code=status.HTTP_200_OK)
async def get_muted(current_user: User = Depends(get_current_user),
                    db: AsyncSession = Depends(get_async_db)) -> dict:
    """List all user IDs whose Echoes you have muted."""
    ids = await list_muted(current_user, db)
    return {"muted_users": [str(i) for i in ids]}
