"""
app/invites/service.py — Invite business logic.

create_invite:
    Validates no duplicate pending invite exists, then creates the row.

list_my_invites:
    Returns all invites sent by the current user. Computes "expired" display
    status for pending invites that have passed their expires_at.

get_invite_by_token:
    Public lookup used by the registration UI.
    Raises 404 if token unknown, 410 if expired or already accepted.
"""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invite import Invite, InviteStatus
from app.models.user import User
from app.invites.schemas import InviteListItem, InviteTokenInfoResponse

_INVITE_TTL_DAYS = 7


async def create_invite(
    inviter: User,
    invitee_email: str,
    db: AsyncSession,
) -> Invite:
    """
    Create a new invite from inviter → invitee_email.
    Raises 409 if a pending invite for this pair already exists.
    """
    # Check for existing pending invite (same inviter + email)
    result = await db.execute(
        select(Invite).where(
            Invite.inviter_id == inviter.user_id,
            Invite.invitee_email == invitee_email,
            Invite.status == InviteStatus.PENDING,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "INVITE_ALREADY_SENT",
                "message": "You already have a pending invite to this email address.",
            },
        )

    now = datetime.now(UTC)
    invite = Invite(
        inviter_id=inviter.user_id,
        invitee_email=invitee_email,
        token=secrets.token_urlsafe(32),
        status=InviteStatus.PENDING,
        expires_at=now + timedelta(days=_INVITE_TTL_DAYS),
    )
    db.add(invite)
    await db.flush()
    return invite


async def list_my_invites(
    inviter: User,
    db: AsyncSession,
) -> list[InviteListItem]:
    """
    Return all invites sent by this user.
    Pending invites past their expires_at are displayed as 'expired'.
    """
    result = await db.execute(
        select(Invite)
        .where(Invite.inviter_id == inviter.user_id)
        .order_by(Invite.created_at.desc())
    )
    invites = result.scalars().all()

    now = datetime.now(UTC)
    items: list[InviteListItem] = []
    for inv in invites:
        display_status = inv.status.value
        if inv.status == InviteStatus.PENDING and inv.expires_at < now:
            display_status = "expired"
        items.append(
            InviteListItem(
                invite_id=inv.invite_id,
                invitee_email=inv.invitee_email,
                status=display_status,
                expires_at=inv.expires_at,
                accepted_at=inv.accepted_at,
                created_at=inv.created_at,
            )
        )
    return items


async def get_invite_by_token(
    token: str,
    db: AsyncSession,
) -> InviteTokenInfoResponse:
    """
    Validate an invite token for the registration UI.

    404 — token not found
    410 — token expired or already accepted
    200 — returns inviter_username + invitee_email for pre-fill
    """
    result = await db.execute(
        select(Invite).where(Invite.token == token)
    )
    invite = result.scalar_one_or_none()

    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "INVITE_NOT_FOUND", "message": "Invite not found."},
        )

    now = datetime.now(UTC)
    if invite.status == InviteStatus.ACCEPTED or invite.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={
                "code": "INVITE_EXPIRED",
                "message": "This invite has already been used or has expired.",
            },
        )

    # Load inviter username
    inviter_result = await db.execute(
        select(User).where(User.user_id == invite.inviter_id)
    )
    inviter = inviter_result.scalar_one()

    return InviteTokenInfoResponse(
        inviter_username=inviter.username,
        invitee_email=invite.invitee_email,
        expires_at=invite.expires_at,
    )
