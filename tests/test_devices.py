"""tests/test_devices.py — Device registration + push notification tests."""

import secrets
import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers
from tests.factories import create_human


def _fake_apns_token() -> str:
    """Generate a realistic-looking 64-hex APNs device token."""
    return secrets.token_hex(32)  # 64 hex chars


def _fake_fcm_token() -> str:
    """Generate a realistic-looking FCM registration token."""
    return secrets.token_urlsafe(140)[:152]


# ------------------------------------------------------------------ #
# POST /devices — register a device token
# ------------------------------------------------------------------ #


async def test_register_apns_device_success(
    client: AsyncClient, db: AsyncSession
) -> None:
    user = await create_human(db)
    await db.commit()

    resp = await client.post(
        "/devices",
        json={"token": _fake_apns_token(), "platform": "apns"},
        headers=auth_headers(user),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["platform"] == "apns"
    assert "device_id" in data
    assert "token" in data
    assert "created_at" in data
    assert "last_seen_at" in data


async def test_register_fcm_device_success(
    client: AsyncClient, db: AsyncSession
) -> None:
    user = await create_human(db)
    await db.commit()

    resp = await client.post(
        "/devices",
        json={"token": _fake_fcm_token(), "platform": "fcm"},
        headers=auth_headers(user),
    )
    assert resp.status_code == 201
    assert resp.json()["platform"] == "fcm"


async def test_register_device_requires_auth(
    client: AsyncClient, db: AsyncSession
) -> None:
    resp = await client.post(
        "/devices",
        json={"token": _fake_apns_token(), "platform": "apns"},
    )
    assert resp.status_code == 401


async def test_register_same_token_is_idempotent(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Re-registering the same token returns 201 and updates last_seen_at."""
    user = await create_human(db)
    await db.commit()
    token = _fake_apns_token()

    resp1 = await client.post(
        "/devices",
        json={"token": token, "platform": "apns"},
        headers=auth_headers(user),
    )
    resp2 = await client.post(
        "/devices",
        json={"token": token, "platform": "apns"},
        headers=auth_headers(user),
    )
    assert resp1.status_code == 201
    assert resp2.status_code == 201
    # Same device_id (upserted, not duplicated)
    assert resp1.json()["device_id"] == resp2.json()["device_id"]


async def test_register_token_reassigns_to_new_user(
    client: AsyncClient, db: AsyncSession
) -> None:
    """A token previously owned by user A is re-assigned to user B on re-registration."""
    user_a = await create_human(db)
    user_b = await create_human(db)
    await db.commit()
    token = _fake_apns_token()

    await client.post(
        "/devices",
        json={"token": token, "platform": "apns"},
        headers=auth_headers(user_a),
    )
    resp = await client.post(
        "/devices",
        json={"token": token, "platform": "apns"},
        headers=auth_headers(user_b),
    )
    assert resp.status_code == 201

    # user_b should now own the token
    devices_b = await client.get("/devices/me", headers=auth_headers(user_b))
    assert any(d["token"] == token for d in devices_b.json())

    # user_a should NOT have it any more
    devices_a = await client.get("/devices/me", headers=auth_headers(user_a))
    assert not any(d["token"] == token for d in devices_a.json())


# ------------------------------------------------------------------ #
# GET /devices/me — list my devices
# ------------------------------------------------------------------ #


async def test_list_devices_empty(client: AsyncClient, db: AsyncSession) -> None:
    user = await create_human(db)
    await db.commit()

    resp = await client.get("/devices/me", headers=auth_headers(user))
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_devices_shows_registered(
    client: AsyncClient, db: AsyncSession
) -> None:
    user = await create_human(db)
    await db.commit()
    token = _fake_fcm_token()

    await client.post(
        "/devices",
        json={"token": token, "platform": "fcm"},
        headers=auth_headers(user),
    )
    resp = await client.get("/devices/me", headers=auth_headers(user))
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["platform"] == "fcm"


async def test_list_devices_requires_auth(
    client: AsyncClient, db: AsyncSession
) -> None:
    resp = await client.get("/devices/me")
    assert resp.status_code == 401


# ------------------------------------------------------------------ #
# DELETE /devices/{token} — unregister a device
# ------------------------------------------------------------------ #


async def test_unregister_device_success(
    client: AsyncClient, db: AsyncSession
) -> None:
    user = await create_human(db)
    await db.commit()
    token = _fake_apns_token()

    await client.post(
        "/devices",
        json={"token": token, "platform": "apns"},
        headers=auth_headers(user),
    )
    resp = await client.delete(f"/devices/{token}", headers=auth_headers(user))
    assert resp.status_code == 204

    # Confirm gone
    devices = await client.get("/devices/me", headers=auth_headers(user))
    assert devices.json() == []


async def test_unregister_not_found_returns_404(
    client: AsyncClient, db: AsyncSession
) -> None:
    user = await create_human(db)
    await db.commit()

    resp = await client.delete(
        f"/devices/{_fake_apns_token()}", headers=auth_headers(user)
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "DEVICE_NOT_FOUND"


async def test_unregister_requires_auth(
    client: AsyncClient, db: AsyncSession
) -> None:
    resp = await client.delete(f"/devices/{_fake_apns_token()}")
    assert resp.status_code == 401


# ------------------------------------------------------------------ #
# Notification triggers — verify social actions still succeed
# ------------------------------------------------------------------ #


async def test_follow_with_device_registered_succeeds(
    client: AsyncClient, db: AsyncSession
) -> None:
    """A follow action completes normally even when the target has a registered device."""
    follower = await create_human(db)
    target = await create_human(db)
    await db.commit()

    # Give target a registered device
    await client.post(
        "/devices",
        json={"token": _fake_apns_token(), "platform": "apns"},
        headers=auth_headers(target),
    )

    resp = await client.post(
        "/follows",
        json={"following_id": str(target.user_id)},
        headers=auth_headers(follower),
    )
    assert resp.status_code == 201


async def test_like_with_device_registered_succeeds(
    client: AsyncClient, db: AsyncSession
) -> None:
    """A like action completes normally even when the post author has a registered device."""
    author = await create_human(db)
    liker = await create_human(db)
    await db.commit()

    # Give author a registered FCM device
    await client.post(
        "/devices",
        json={"token": _fake_fcm_token(), "platform": "fcm"},
        headers=auth_headers(author),
    )

    # author creates a Life post
    post_resp = await client.post(
        "/posts",
        json={"content_text": "Hello world", "is_pulse_post": False},
        headers=auth_headers(author),
    )
    post_id = post_resp.json()["post_id"]

    resp = await client.post(
        f"/likes/{post_id}",
        headers=auth_headers(liker),
    )
    assert resp.status_code == 201


async def test_echo_with_device_registered_succeeds(
    client: AsyncClient, db: AsyncSession
) -> None:
    """An echo action completes normally even when the post author has a registered device."""
    from tests.factories import create_business

    # Pulse posts come from Business/Meme/Info accounts — create that setup
    human_owner = await create_human(db)
    pulse_author = await create_business(db, linked_human=human_owner)
    echoer = await create_human(db)
    await db.commit()

    # Give pulse_author a registered APNs device
    await client.post(
        "/devices",
        json={"token": _fake_apns_token(), "platform": "apns"},
        headers=auth_headers(pulse_author),
    )

    # pulse_author creates a Pulse post (Business accounts always create Pulse posts)
    post_resp = await client.post(
        "/posts",
        json={"content_text": "Important take"},
        headers=auth_headers(pulse_author),
    )
    assert post_resp.status_code == 201
    post_id = post_resp.json()["post_id"]

    # echoer (verified Human) echoes the Pulse post
    resp = await client.post(
        "/echoes",
        json={"post_id": post_id},
        headers=auth_headers(echoer),
    )
    assert resp.status_code == 201
