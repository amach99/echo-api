"""app/invites/schemas.py — Pydantic schemas for the invite endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class SendInviteRequest(BaseModel):
    invitee_email: EmailStr


class InviteResponse(BaseModel):
    """Returned after sending an invite (POST /invites)."""

    invite_id: uuid.UUID
    invitee_email: str
    token: str
    status: str
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class InviteListItem(BaseModel):
    """Single item in GET /invites/me list."""

    invite_id: uuid.UUID
    invitee_email: str
    status: str        # may be "expired" even if DB says "pending" but past expires_at
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InviteTokenInfoResponse(BaseModel):
    """Returned by GET /invites/{token} — used by the registration UI to pre-fill."""

    inviter_username: str
    invitee_email: str
    expires_at: datetime
