"""
app/echoes/router.py — Echo (Human Firewall) endpoints.
All write actions gated by require_age_verified.
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_async_db
from app.echoes.schemas import EchoCreate, EchoResponse
from app.echoes.service import create_echo, delete_echo
from app.middleware.age_verification import require_age_verified
from app.models.user import User
from app.notifications.adapter import PushAdapter, get_push_adapter
from app.notifications.service import dispatch_push, get_tokens_for_post_author

router = APIRouter(
    prefix="/echoes",
    tags=["echoes"],
    dependencies=[Depends(require_age_verified)],
)


@router.post("", response_model=EchoResponse, status_code=status.HTTP_201_CREATED)
async def echo_post(
    payload: EchoCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
    push_adapter: PushAdapter = Depends(get_push_adapter),
) -> EchoResponse:
    """
    Echo a Pulse post into your followers' Life Feeds.
    Only Human accounts may echo. Rate: governed by general write limit.
    """
    echo = await create_echo(current_user, payload.post_id, db)

    # Notify the post author — look up tokens while DB session is open
    tokens = await get_tokens_for_post_author(post_id=payload.post_id, db=db)
    if tokens:
        background_tasks.add_task(
            dispatch_push,
            adapter=push_adapter,
            device_tokens=tokens,
            title="New echo",
            body=f"@{current_user.username} echoed your post",
            data={"type": "echo", "post_id": str(payload.post_id)},
        )

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
