"""
app/models/invite.py — Invite ORM model.

Each row represents one invitation sent from an Echo user to an email address.
Tokens are cryptographically random (secrets.token_urlsafe) and expire after 7 days.
The UNIQUE(inviter_id, invitee_email) constraint prevents duplicate pending invites.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class InviteStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"


# PostgreSQL native enum — values_callable ensures DB stores lowercase strings
invite_status_pg_enum = Enum(
    InviteStatus,
    name="invite_status_enum",
    create_type=True,
    values_callable=lambda obj: [e.value for e in obj],
)


class Invite(Base):
    __tablename__ = "invites"

    invite_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    inviter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    invitee_email: Mapped[str] = mapped_column(Text, nullable=False)

    # Cryptographically random URL-safe token — secrets.token_urlsafe(32)
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    status: Mapped[InviteStatus] = mapped_column(
        invite_status_pg_enum,
        nullable=False,
        default=InviteStatus.PENDING,
        server_default=InviteStatus.PENDING.value,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ------------------------------------------------------------------ #
    # Relationships
    # ------------------------------------------------------------------ #
    inviter: Mapped["User"] = relationship(  # type: ignore[name-defined] # noqa: F821
        "User", foreign_keys=[inviter_id]
    )

    __table_args__ = (
        # One pending invite per inviter+email pair — enforced at DB level
        __import__("sqlalchemy").UniqueConstraint(
            "inviter_id", "invitee_email", name="uq_invites_inviter_email"
        ),
    )
