"""
app/echoes/router.py — Echo (Human Firewall) endpoints.
All write actions gated by require_age_verified.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_async_db
from app.echoes.schemas import EchoCreate, EchoResponse
from app.echoes.service import create_echo, delete_echo
from app.middleware.age_verification import require_age_verified
from app.models.user import User

router = APIRouter(
    prefix="/echoes",
    tags=["echoes"],
    dependencies=[Depends(require_age_verified)],
)


@router.post("", response_model=EchoResponse, status_code=status.HTTP_201_CREATED)
async def echo_post(
    payload: EchoCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> EchoResponse:
    """
    Echo a Pulse post into your followers' Life Feeds.
    Only Human accounts may echo. Rate: governed by general write limit.
    """
    echo = await create_echo(current_user, payload.post_id, db)
    return EchoResponse(
        echoer_id=echo.echoer_id,
        post_id=echo.post_id,
        created_at=echo.created_at,
    )


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unecho_post(
    post_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> None:
    """Remove an echo — the post will no longer appear in followers' Life Feeds."""
    await delete_echo(current_user, post_id, db)
