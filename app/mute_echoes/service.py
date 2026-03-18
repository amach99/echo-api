import uuid
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.mute_echo import MuteEcho
from app.models.user import User


async def mute_echoes(user: User, target_id: uuid.UUID, db: AsyncSession) -> MuteEcho:
    if user.user_id == target_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail={"code": "CANNOT_MUTE_SELF"})
    existing = await db.execute(select(MuteEcho).where(
        MuteEcho.user_id == user.user_id, MuteEcho.muted_user_id == target_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail={"code": "ALREADY_MUTED"})
    mute = MuteEcho(user_id=user.user_id, muted_user_id=target_id)
    db.add(mute)
    await db.flush()
    return mute


async def unmute_echoes(user: User, target_id: uuid.UUID, db: AsyncSession) -> None:
    result = await db.execute(select(MuteEcho).where(
        MuteEcho.user_id == user.user_id, MuteEcho.muted_user_id == target_id))
    mute = result.scalar_one_or_none()
    if not mute:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"code": "MUTE_NOT_FOUND"})
    await db.delete(mute)


async def list_muted(user: User, db: AsyncSession) -> list[uuid.UUID]:
    result = await db.execute(
        select(MuteEcho.muted_user_id).where(MuteEcho.user_id == user.user_id))
    return [row[0] for row in result.fetchall()]
