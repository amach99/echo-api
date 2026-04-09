"""
app/models/__init__.py — Re-export all models so Alembic can discover them.

Import order matters for FK resolution.
"""

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.comment import Comment
from app.models.device import Device, Platform
from app.models.echo import Echo
from app.models.follow import Follow
from app.models.invite import Invite, InviteStatus
from app.models.like import Like
from app.models.mute_echo import MuteEcho
from app.models.post import Post
from app.models.post_media import PostMedia
from app.models.user import AccountType, User
from app.models.vote import Vote

__all__ = [
    "Base",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "User",
    "AccountType",
    "Post",
    "PostMedia",
    "Comment",
    "Follow",
    "Like",
    "Vote",
    "Echo",
    "MuteEcho",
    "Invite",
    "InviteStatus",
    "Device",
    "Platform",
]
