"""
app/models/device.py — Device push token model.

Stores per-user APNs (iOS) and FCM (Android) push tokens.
A single token is unique globally — if the same token arrives from a
different user (device hand-off / account switch) the row is upserted
to the new owner so the old user stops receiving notifications on that device.

last_seen_at is bumped every time the app re-registers the token on launch,
which lets the backend prune stale tokens if needed in future.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Platform(str, enum.Enum):
    APNS = "apns"   # Apple Push Notification service (iOS)
    FCM  = "fcm"    # Firebase Cloud Messaging (Android)


# PostgreSQL native enum
platform_pg_enum = Enum(
    Platform,
    name="platform_enum",
    create_type=True,
    values_callable=lambda obj: [e.value for e in obj],
)


class Device(Base):
    __tablename__ = "devices"

    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The device push token issued by APNs or FCM
    token: Mapped[str] = mapped_column(String(512), nullable=False, unique=True, index=True)

    platform: Mapped[Platform] = mapped_column(platform_pg_enum, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # ------------------------------------------------------------------ #
    # Relationships
    # ------------------------------------------------------------------ #
    user: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User", foreign_keys=[user_id]
    )
