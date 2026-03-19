"""
app/notifications/service.py — Push notification helpers.

Design principle: DB lookups happen in the main request handler while the
session is open. Only plain values (token strings, platform strings) are
passed into BackgroundTasks — background tasks never touch the DB.

Usage pattern in routers:
    tokens = await get_tokens_for_user(user_id=target_id, db=db)
    if tokens:
        background_tasks.add_task(
            dispatch_push,
            adapter=push_adapter,
            device_tokens=tokens,
            title="New Follower",
            body=f"@{current_user.username} started following you",
        )
"""

import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comment import Comment
from app.models.device import Device
from app.models.post import Post
from app.models.user import User
from app.notifications.adapter import PushAdapter

# Matches @username patterns — 3-30 word chars, case-insensitive
_MENTION_RE = re.compile(r"@(\w{3,30})")


async def get_tokens_for_user(
    user_id: uuid.UUID,
    db: AsyncSession,
) -> list[tuple[str, str]]:
    """
    Return (token, platform) pairs for all devices registered to user_id.
    Returns empty list if user has no registered devices.
    """
    result = await db.execute(
        select(Device.token, Device.platform).where(Device.user_id == user_id)
    )
    return [(row.token, row.platform.value) for row in result.all()]


async def get_tokens_for_post_author(
    post_id: uuid.UUID,
    db: AsyncSession,
) -> list[tuple[str, str]]:
    """
    Return (token, platform) pairs for the author of the given post.
    Used for like and echo notifications.
    Returns empty list if post not found or author has no devices.
    """
    post_result = await db.execute(
        select(Post.author_id).where(Post.post_id == post_id)
    )
    row = post_result.first()
    if row is None:
        return []
    return await get_tokens_for_user(user_id=row.author_id, db=db)


def extract_mentions(text: str) -> list[str]:
    """
    Extract unique lowercased @usernames from comment text.
    Returns at most 30 distinct usernames to prevent mention spam.
    """
    matches = _MENTION_RE.findall(text)
    seen: list[str] = []
    seen_set: set[str] = set()
    for m in matches:
        lower = m.lower()
        if lower not in seen_set:
            seen_set.add(lower)
            seen.append(lower)
        if len(seen) >= 30:
            break
    return seen


async def get_tokens_for_comment_author(
    comment_id: uuid.UUID,
    db: AsyncSession,
) -> tuple[list[tuple[str, str]], uuid.UUID | None]:
    """
    Return (tokens, author_user_id) for the author of the given comment.
    Caller uses author_user_id to guard against self-notify.
    Returns ([], None) if comment not found or author has no devices.
    """
    result = await db.execute(
        select(Comment.author_id).where(Comment.comment_id == comment_id)
    )
    row = result.first()
    if row is None:
        return [], None
    tokens = await get_tokens_for_user(user_id=row.author_id, db=db)
    return tokens, row.author_id


async def get_tokens_for_usernames(
    usernames: list[str],
    db: AsyncSession,
) -> dict[str, list[tuple[str, str]]]:
    """
    Return {lowercased_username: [(token, platform), ...]} for each username.
    Single JOIN query — no N+1.
    Usernames that have no devices are excluded from the result dict.
    """
    if not usernames:
        return {}

    stmt = (
        select(User.username, Device.token, Device.platform)
        .join(Device, Device.user_id == User.user_id)
        .where(func.lower(User.username).in_(usernames))
    )
    rows = (await db.execute(stmt)).all()

    result: dict[str, list[tuple[str, str]]] = {}
    for row in rows:
        key = row.username.lower()
        result.setdefault(key, []).append((row.token, row.platform.value))
    return result


async def dispatch_push(
    adapter: PushAdapter,
    device_tokens: list[tuple[str, str]],
    title: str,
    body: str,
    data: dict | None = None,
) -> None:
    """
    Dispatch a push notification to all provided device tokens.
    Called as a FastAPI BackgroundTask — errors are logged, never raised.
    Each token is attempted independently; one failure doesn't abort the rest.
    """
    for token, platform in device_tokens:
        try:
            await adapter.send(
                token=token,
                platform=platform,
                title=title,
                body=body,
                data=data,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[Notifications] dispatch error token={token[:16]}...: {exc}")
