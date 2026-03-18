"""
app/models/mute_echo.py — Per-friend Mute Echoes setting.

When user_id mutes muted_user_id, that friend's Echoed Pulse content
is hidden from user_id's Life Feed.

Their original Life posts are NOT affected — only their Echoes are hidden.

CRITICAL: This table MUST be consulted on EVERY Life Feed query.
Skipping it is a CRITICAL bug (RULES.md invariant 5).
"""

import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class MuteEcho(Base):
    __tablename__ = "mute_echoes"

    # The user who has applied the mute
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    # The followed Human whose Echoes are being suppressed
    muted_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )

    user: Mapped["User"] = relationship(  # type: ignore[name-defined] # noqa: F821
        "User", foreign_keys=[user_id], back_populates="muted_echoes"
    )
    muted_user: Mapped["User"] = relationship(  # type: ignore[name-defined] # noqa: F821
        "User", foreign_keys=[muted_user_id]
    )
