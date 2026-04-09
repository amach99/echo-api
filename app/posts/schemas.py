"""
app/posts/schemas.py — Pydantic v2 schemas for post endpoints.

IMPORTANT: is_pulse_post is NOT in PostCreate.
It is set server-side from author.account_type at write time. Never from client input.
"""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, model_validator


class MediaItem(BaseModel):
    """A single media attachment on a post (image or video)."""

    media_url: str
    position: int

    model_config = {"from_attributes": True}


class PostCreate(BaseModel):
    content_text: str | None = Field(
        default=None,
        max_length=5000,
        description="Text content of the post",
    )
    # Up to 10 ordered S3 URLs.  position is implied by list order (index 0 = cover).
    media_urls: list[Annotated[str, Field(max_length=2048)]] | None = Field(
        default=None,
        max_length=10,
        description="Ordered S3 URLs for attached media (max 10)",
    )

    @model_validator(mode="after")
    def at_least_one_field(self) -> "PostCreate":
        if not self.content_text and not self.media_urls:
            raise ValueError("A post must have either content_text or media_urls.")
        return self


class PostUpdate(BaseModel):
    content_text: str | None = Field(
        default=None,
        max_length=5000,
        description="Updated text content of the post",
    )


class PostResponse(BaseModel):
    post_id: uuid.UUID
    author_id: uuid.UUID
    author_username: str
    content_text: str | None
    media: list[MediaItem] = []
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
