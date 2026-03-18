"""
app/posts/schemas.py — Pydantic v2 schemas for post endpoints.

IMPORTANT: is_pulse_post is NOT in PostCreate.
It is set server-side from author.account_type at write time. Never from client input.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class PostCreate(BaseModel):
    content_text: str | None = Field(
        default=None,
        max_length=5000,
        description="Text content of the post",
    )
    media_url: str | None = Field(
        default=None,
        max_length=2048,
        description="S3 URL for attached media (image or video)",
    )

    @model_validator(mode="after")
    def at_least_one_field(self) -> "PostCreate":
        if not self.content_text and not self.media_url:
            raise ValueError("A post must have either content_text or media_url.")
        return self


class PostResponse(BaseModel):
    post_id: uuid.UUID
    author_id: uuid.UUID
    author_username: str
    content_text: str | None
    media_url: str | None
    is_pulse_post: bool
    created_at: datetime

    # Life Feed only (is_pulse_post = False)
    like_count: int | None = None

    # Pulse Feed only (is_pulse_post = True)
    net_score: int | None = None

    # Echo context — populated when post appears via an Echo in Life Feed
    echoed_by_username: str | None = None
    echoed_at: datetime | None = None

    model_config = {"from_attributes": True}
