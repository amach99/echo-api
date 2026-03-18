"""
app/models/vote.py — Pulse Feed interaction (upvote/downvote).
Net score = SUM(vote_value) per post — drives Pulse Feed ranking.
Scores are internal only; NOT displayed publicly on profiles.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, SmallInteger, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Vote(Base):
    __tablename__ = "votes"
    __table_args__ = (
        CheckConstraint("vote_value IN (1, -1)", name="ck_vote_value"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("posts.post_id", ondelete="CASCADE"),
        primary_key=True,
    )
    # +1 = Upvote | -1 = Downvote
    vote_value: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="votes")  # type: ignore[name-defined] # noqa: F821
    post: Mapped["Post"] = relationship("Post", back_populates="votes")  # type: ignore[name-defined] # noqa: F821
