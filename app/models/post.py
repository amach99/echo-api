"""
app/models/post.py — Post ORM model.

is_pulse_post is set SERVER-SIDE based on author.account_type at write time.
It is NEVER accepted from client input.

Routing:
  is_pulse_post = False → Life Feed  (Human posts, chronological)
  is_pulse_post = True  → Pulse Feed (Business/Meme/Info, net-score ranked)
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Post(Base):
    __tablename__ = "posts"

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )

    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Feed routing flag — set server-side only from author.account_type.
    # False = Life Feed post | True = Pulse Feed post
    is_pulse_post: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ------------------------------------------------------------------ #
    # Relationships
    # ------------------------------------------------------------------ #
    author: Mapped["User"] = relationship("User", back_populates="posts")  # type: ignore[name-defined] # noqa: F821

    likes: Mapped[list["Like"]] = relationship(  # type: ignore[name-defined] # noqa: F821
        "Like", back_populates="post", cascade="all, delete-orphan"
    )
    votes: Mapped[list["Vote"]] = relationship(  # type: ignore[name-defined] # noqa: F821
        "Vote", back_populates="post", cascade="all, delete-orphan"
    )
    echoes: Mapped[list["Echo"]] = relationship(  # type: ignore[name-defined] # noqa: F821
        "Echo", back_populates="post", cascade="all, delete-orphan"
    )
