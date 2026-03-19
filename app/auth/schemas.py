"""
app/auth/schemas.py — Pydantic v2 schemas for authentication endpoints.
All inputs validated before any business logic runs (Rule 6).
"""

import uuid
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


class RegisterRequest(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=30,
        pattern=r"^[a-zA-Z0-9_]+$",
        description="3-30 chars, alphanumeric and underscores only",
    )
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    account_type: Literal["human", "business", "meme", "social_info"] = "human"

    # Required for non-Human accounts — links to the Human representative
    linked_human_id: uuid.UUID | None = None

    # Optional — marks the referring invite as accepted on successful registration.
    # Invalid or expired tokens are silently ignored and never block registration.
    invite_token: str | None = None

    @model_validator(mode="after")
    def linked_human_required_for_non_human(self) -> "RegisterRequest":
        if self.account_type != "human" and self.linked_human_id is None:
            raise ValueError(
                "linked_human_id is required for Business, Meme, and Social Info accounts."
            )
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class UserPublicResponse(BaseModel):
    user_id: uuid.UUID
    username: str
    account_type: str
    is_verified_human: bool
    bio: str | None
    profile_picture_url: str | None

    model_config = {"from_attributes": True}
