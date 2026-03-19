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

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.post import Post
from app.notifications.adapter import PushAdapter


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
