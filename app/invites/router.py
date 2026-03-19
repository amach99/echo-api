"""
app/invites/router.py — Invite Friends endpoints.

Route registration order is intentional:
  GET /invites/me is registered BEFORE GET /invites/{token} so that the
  literal string "me" is never mistakenly treated as a token value.

POST /invites          requires auth — create + email an invite
GET  /invites/me       requires auth — list all invites sent by current user
GET  /invites/{token}  public — validate token (used by registration UI)
"""

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_async_db
from app.email.adapter import EmailAdapter, get_email_adapter
from app.invites.schemas import (
    InviteListItem,
    InviteResponse,
    InviteTokenInfoResponse,
    SendInviteRequest,
)
from app.invites.service import create_invite, get_invite_by_token, list_my_invites
from app.models.user import User

router = APIRouter(prefix="/invites", tags=["invites"])


# ------------------------------------------------------------------ #
# POST /invites — send an invite
# ------------------------------------------------------------------ #


@router.post(
    "",
    response_model=InviteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send an email invite to a friend",
)
async def send_invite(
    payload: SendInviteRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
    email_adapter: EmailAdapter = Depends(get_email_adapter),
) -> InviteResponse:
    """
    Creates an invite token and emails the invite link to the friend.
    Email is sent as a background task — the response is immediate
    regardless of email delivery speed.
    """
    invite = await create_invite(
        inviter=current_user,
        invitee_email=str(payload.invitee_email),
        db=db,
    )

    # Fire-and-forget — never blocks the HTTP response
    background_tasks.add_task(
        email_adapter.send_invite,
        to=str(payload.invitee_email),
        inviter_username=current_user.username,
        token=invite.token,
    )

    return InviteResponse.model_validate(invite)


# ------------------------------------------------------------------ #
# GET /invites/me — list sent invites (BEFORE /{token} to avoid collision)
# ------------------------------------------------------------------ #


@router.get(
    "/me",
    response_model=list[InviteListItem],
    summary="List all invites I have sent",
)
async def get_my_invites(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> list[InviteListItem]:
    """Returns all invites sent by the authenticated user, newest first."""
    return await list_my_invites(inviter=current_user, db=db)


# ------------------------------------------------------------------ #
# GET /invites/{token} — validate a token (public)
# ------------------------------------------------------------------ #


@router.get(
    "/{token}",
    response_model=InviteTokenInfoResponse,
    summary="Validate an invite token",
)
async def validate_invite_token(
    token: str,
    db: AsyncSession = Depends(get_async_db),
) -> InviteTokenInfoResponse:
    """
    Called by the registration UI to pre-fill the email field and show the
    inviter's name. Returns 404 if the token doesn't exist, 410 if expired
    or already accepted.
    """
    return await get_invite_by_token(token=token, db=db)
