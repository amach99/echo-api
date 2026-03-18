"""
app/feeds/schemas.py — Feed response schemas.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class LifeFeedItem(BaseModel):
    post_id: uuid.UUID
    author_id: uuid.UUID
    author_username: str
    content_text: str | None
    media_url: str | None
    is_pulse_post: bool
    created_at: datetime
    like_count: int = 0

    # Populated when item appears via an Echo
    echoed_by_username: str | None = None
    echoed_at: datetime | None = None

    model_config = {"from_attributes": True}


class PulseFeedItem(BaseModel):
    post_id: uuid.UUID
    author_id: uuid.UUID
    author_username: str
    content_text: str | None
    media_url: str | None
    is_pulse_post: bool
    created_at: datetime
    net_score: int = 0

    model_config = {"from_attributes": True}


class FeedResponse(BaseModel):
    items: list[Any]            # LifeFeedItem | PulseFeedItem
    next_cursor: str | None     # opaque cursor for pagination
