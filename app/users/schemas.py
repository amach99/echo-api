"""app/users/schemas.py — Pydantic schemas for user profile endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class UserPublicResponse(BaseModel):
    """
    Public profile returned for any user.
    Intentionally excludes: email, password_hash, reputation_score.
    """

    user_id: uuid.UUID
    username: str
    account_type: str
    is_verified_human: bool
    bio: str | None
    profile_picture_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdateRequest(BaseModel):
    """
    Fields the user may update on their own profile.
    Any field sent as null is treated as a no-op (existing value preserved).
    is_verified_human is NOT included — it is set exclusively by the verification callback.
    """

    bio: str | None = Field(default=None, max_length=500)
    profile_picture_url: str | None = Field(default=None, max_length=2048)
