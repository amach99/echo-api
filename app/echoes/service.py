"""
app/echoes/service.py — Human Firewall echo logic.

An Echo is the ONLY way a Pulse post can enter a Human's Life Feed.

Validations (all enforced here as defense-in-depth, even though
the age gate middleware already runs upstream):
  1. echoer.account_type == 'human'  — only Humans can echo
  2. echoer.is_verified_human == True
  3. target post must be is_pulse_post = True
  4. no duplicate echo (409 on repeat)
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.echo import Echo
from app.models.post import Post
from app.models.user import AccountType, User


async def create_echo(
    echoer: User,
    post_id: uuid.UUID,
    db: AsyncSession,
) -> Echo:
    # Validation 1: Only Human accounts can echo
    if echoer.account_type != AccountType.HUMAN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ECHO_REQUIRES_HUMAN_ACCOUNT",
                "message": "Only Human accounts can Echo posts into the Life Feed.",
            },
        )

    # Validation 2: Must be ID-verified (defense-in-depth)
    if not echoer.is_verified_human:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "AGE_VERIFICATION_REQUIRED",
                "message": "You must complete 18+ ID verification before echoing.",
            },
        )

    # Validation 3: Target post must be a Pulse post
    result = await db.execute(select(Post).where(Post.post_id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "POST_NOT_FOUND", "message": "Post not found."},
        )
    if not post.is_pulse_post:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "CANNOT_ECHO_LIFE_POST",
                "message": "Only Pulse posts can be Echoed into the Life Feed.",
            },
        )

    # Validation 4: No duplicate echo
    existing = await db.execute(
        select(Echo).where(
            Echo.echoer_id == echoer.user_id,
            Echo.post_id == post_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ALREADY_ECHOED", "message": "You have already echoed this post."},
        )

    echo = Echo(echoer_id=echoer.user_id, post_id=post_id)
    db.add(echo)
    await db.flush()
    return echo


async def delete_echo(
    echoer: User,
    post_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    result = await db.execute(
        select(Echo).where(
            Echo.echoer_id == echoer.user_id,
            Echo.post_id == post_id,
        )
    )
    echo = result.scalar_one_or_none()
    if not echo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ECHO_NOT_FOUND", "message": "Echo not found."},
        )
    await db.delete(echo)
