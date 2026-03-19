"""app/comments/schemas.py — Pydantic schemas for the comments endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CreateCommentRequest(BaseModel):
    content_text: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Comment body — maximum 500 characters.",
    )
    parent_id: uuid.UUID | None = Field(
        default=None,
        description="Set to reply to an existing comment. Omit for a top-level comment.",
    )


class CommentResponse(BaseModel):
    comment_id: uuid.UUID
    post_id: uuid.UUID
    author_id: uuid.UUID
    author_username: str
    parent_id: uuid.UUID | None
    content_text: str
    reply_count: int = 0   # populated for top-level list; always 0 for individual items
    created_at: datetime

    model_config = {"from_attributes": True}
