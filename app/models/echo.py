"""
app/models/echo.py — The "Human Firewall" bridge table.

An Echo is the ONLY mechanism by which a Pulse post (Business/Meme/Info)
can appear in a Human user's Life Feed.

Rules enforced at the service layer:
  1. echoer.account_type MUST be 'human'
  2. echoer.is_verified_human MUST be True
  3. Target post MUST be a Pulse post (is_pulse_post = True)
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Echo(Base):
    __tablename__ = "echoes"

    # The Human user performing the repost — MUST be account_type = 'human'
    echoer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("posts.post_id", ondelete="CASCADE"),
        primary_key=True,
    )
    # echo.created_at is used as the sort timestamp in the Life Feed,
    # NOT post.created_at — the echo appears at the time the Human vouched for it.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    echoer: Mapped["User"] = relationship(  # type: ignore[name-defined] # noqa: F821
        "User", foreign_keys=[echoer_id], back_populates="echoes"
    )
    post: Mapped["Post"] = relationship("Post", back_populates="echoes")  # type: ignore[name-defined] # noqa: F821
