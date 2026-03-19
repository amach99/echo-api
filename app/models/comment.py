"""
app/models/comment.py — Comment ORM model.

Supports threaded replies one level deep (top-level comment + replies).
  parent_id IS NULL  → top-level comment on a post
  parent_id SET      → reply to an existing comment

Both author and post deletions cascade via ondelete="CASCADE".
Replies also cascade when their parent comment is deleted.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Comment(Base):
    __tablename__ = "comments"

    comment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("posts.post_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # NULL  → top-level comment
    # SET   → reply; must reference a comment on the same post_id
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comments.comment_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    content_text: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ------------------------------------------------------------------ #
    # Relationships
    # ------------------------------------------------------------------ #

    author: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User", back_populates="comments"
    )

    post: Mapped["Post"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Post", back_populates="comments"
    )

    # Self-referential adjacency list.
    # remote_side must point to the PK (comment_id), not the FK (parent_id).
    parent: Mapped["Comment | None"] = relationship(
        "Comment",
        remote_side="Comment.comment_id",
        back_populates="replies",
        foreign_keys=[parent_id],
    )

    replies: Mapped[list["Comment"]] = relationship(
        "Comment",
        back_populates="parent",
        foreign_keys="Comment.parent_id",
        cascade="all, delete-orphan",
    )
