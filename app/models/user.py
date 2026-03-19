"""
app/models/user.py — User ORM model.

The is_verified_human flag is the Texas SB 2420 gatekeeper.
It is ONLY set server-side via the ID verification callback — never from client input.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AccountType(str, enum.Enum):
    HUMAN = "human"
    BUSINESS = "business"
    MEME = "meme"
    SOCIAL_INFO = "social_info"


# PostgreSQL native enum type — matches SCHEMA.sql exactly.
# values_callable ensures Postgres enum uses .value strings ("human", "business", ...)
# instead of Python member names ("HUMAN", "BUSINESS", ...).
account_type_pg_enum = Enum(
    AccountType,
    name="account_type_enum",
    create_type=True,   # Alembic will emit CREATE TYPE
    values_callable=lambda obj: [e.value for e in obj],
)


class User(Base):
    __tablename__ = "users"

    # Primary key
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    username: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    account_type: Mapped[AccountType] = mapped_column(
        account_type_pg_enum,
        nullable=False,
        default=AccountType.HUMAN,
        server_default=AccountType.HUMAN.value,
    )

    # ------------------------------------------------------------------ #
    # Texas SB 2420 / Digital Authenticity Act compliance flag.
    # Set TRUE only after successful Level 3 Government ID verification.
    # NEVER accept this from client input. Server-side only.
    # ------------------------------------------------------------------ #
    is_verified_human: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # Internal Pulse Feed ranking signal. NOT exposed publicly on profiles.
    reputation_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_picture_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Hashed password — added here (SCHEMA.sql omitted this; required for auth)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Self-referential FK: Business/Meme accounts link to their Human representative
    linked_human_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    # ------------------------------------------------------------------ #
    # Relationships
    # ------------------------------------------------------------------ #
    linked_human: Mapped["User | None"] = relationship(
        "User", remote_side="User.user_id", foreign_keys=[linked_human_id]
    )

    posts: Mapped[list["Post"]] = relationship(  # type: ignore[name-defined] # noqa: F821
        "Post", back_populates="author", cascade="all, delete-orphan"
    )
    echoes: Mapped[list["Echo"]] = relationship(  # type: ignore[name-defined] # noqa: F821
        "Echo", foreign_keys="Echo.echoer_id", back_populates="echoer",
        cascade="all, delete-orphan",
    )
    # Follows where this user is the follower
    following: Mapped[list["Follow"]] = relationship(  # type: ignore[name-defined] # noqa: F821
        "Follow", foreign_keys="Follow.follower_id", back_populates="follower",
        cascade="all, delete-orphan",
    )
    # Follows where this user is being followed
    followers: Mapped[list["Follow"]] = relationship(  # type: ignore[name-defined] # noqa: F821
        "Follow", foreign_keys="Follow.following_id", back_populates="following_user",
        cascade="all, delete-orphan",
    )
    likes: Mapped[list["Like"]] = relationship(  # type: ignore[name-defined] # noqa: F821
        "Like", back_populates="user", cascade="all, delete-orphan"
    )
    votes: Mapped[list["Vote"]] = relationship(  # type: ignore[name-defined] # noqa: F821
        "Vote", back_populates="user", cascade="all, delete-orphan"
    )
    # Mutes this user has placed on others
    muted_echoes: Mapped[list["MuteEcho"]] = relationship(  # type: ignore[name-defined] # noqa: F821
        "MuteEcho", foreign_keys="MuteEcho.user_id", back_populates="user",
        cascade="all, delete-orphan",
    )

    @property
    def is_pulse_account(self) -> bool:
        """Business/Meme/Social Info accounts post to Pulse only."""
        return self.account_type in (
            AccountType.BUSINESS, AccountType.MEME, AccountType.SOCIAL_INFO
        )
