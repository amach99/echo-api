"""
app/devices/service.py — Device push token management.

register_device:
    Upserts by token value. If the token already exists for this user,
    updates last_seen_at (idempotent re-registration on each app launch).
    If the token belongs to a different user (device hand-off), re-assigns it
    to the new user and resets last_seen_at.

unregister_device:
    Deletes the device row for this user. Returns 404 if not found.
    Tokens are scoped to the requesting user for security — a user can
    only unregister their own tokens.

list_user_devices:
    Returns all devices registered to the requesting user.
"""

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device, Platform
from app.models.user import User


async def register_device(
    user: User,
    token: str,
    platform: str,
    db: AsyncSession,
) -> Device:
    """
    Upsert a device token. Idempotent — safe to call on every app launch.
    """
    result = await db.execute(select(Device).where(Device.token == token))
    device = result.scalar_one_or_none()

    now = datetime.now(UTC)

    if device is not None:
        # Token exists — re-assign to current user and bump last_seen_at
        device.user_id = user.user_id
        device.platform = Platform(platform)
        device.last_seen_at = now
        await db.flush()
        return device

    # New token — create row
    device = Device(
        user_id=user.user_id,
        token=token,
        platform=Platform(platform),
        last_seen_at=now,
    )
    db.add(device)
    await db.flush()
    return device


async def unregister_device(
    user: User,
    token: str,
    db: AsyncSession,
) -> None:
    """
    Delete a device token registered to this user.
    Raises 404 if the token doesn't exist or belongs to another user.
    """
    result = await db.execute(
        select(Device).where(
            Device.token == token,
            Device.user_id == user.user_id,
        )
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DEVICE_NOT_FOUND", "message": "Device token not found."},
        )
    await db.delete(device)


async def list_user_devices(
    user: User,
    db: AsyncSession,
) -> list[Device]:
    """Return all devices registered to the requesting user."""
    result = await db.execute(
        select(Device)
        .where(Device.user_id == user.user_id)
        .order_by(Device.last_seen_at.desc())
    )
    return list(result.scalars().all())
