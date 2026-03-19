"""tests/test_users.py — User profile endpoint tests."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers
from tests.factories import create_human


async def test_get_user_profile_success(
    client: AsyncClient, db: AsyncSession
) -> None:
    user = await create_human(db)
    await db.commit()

    resp = await client.get(f"/users/{user.user_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == str(user.user_id)
    assert data["username"] == user.username
    assert data["account_type"] == "human"
    assert data["is_verified_human"] is True


async def test_get_user_profile_not_found(
    client: AsyncClient, db: AsyncSession
) -> None:
    resp = await client.get(f"/users/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "USER_NOT_FOUND"


async def test_get_me_requires_auth(
    client: AsyncClient, db: AsyncSession
) -> None:
    resp = await client.get("/users/me")
    assert resp.status_code == 401


async def test_get_me_returns_current_user(
    client: AsyncClient, db: AsyncSession
) -> None:
    user = await create_human(db)
    await db.commit()

    resp = await client.get("/users/me", headers=auth_headers(user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == str(user.user_id)
    assert data["username"] == user.username
    assert data["is_verified_human"] is True


async def test_update_me_bio(client: AsyncClient, db: AsyncSession) -> None:
    user = await create_human(db)
    await db.commit()

    resp = await client.patch(
        "/users/me",
        json={"bio": "Hello, I am a test user"},
        headers=auth_headers(user),
    )
    assert resp.status_code == 200
    assert resp.json()["bio"] == "Hello, I am a test user"


async def test_update_me_profile_picture_url(
    client: AsyncClient, db: AsyncSession
) -> None:
    user = await create_human(db)
    await db.commit()

    url = "https://echo-media-dev.s3.amazonaws.com/avatars/user123.jpg"
    resp = await client.patch(
        "/users/me",
        json={"profile_picture_url": url},
        headers=auth_headers(user),
    )
    assert resp.status_code == 200
    assert resp.json()["profile_picture_url"] == url


async def test_update_me_requires_auth(
    client: AsyncClient, db: AsyncSession
) -> None:
    resp = await client.patch("/users/me", json={"bio": "test"})
    assert resp.status_code == 401


async def test_update_me_bio_too_long(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Bio is capped at 500 chars — 501 chars returns 422."""
    user = await create_human(db)
    await db.commit()

    resp = await client.patch(
        "/users/me",
        json={"bio": "x" * 501},
        headers=auth_headers(user),
    )
    assert resp.status_code == 422


async def test_update_me_null_fields_are_ignored(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Sending null for bio should not overwrite an existing bio."""
    user = await create_human(db)
    await db.commit()

    # First set a bio
    await client.patch(
        "/users/me",
        json={"bio": "My original bio"},
        headers=auth_headers(user),
    )
    # Then send null — should NOT clear it
    resp = await client.patch(
        "/users/me",
        json={"bio": None},
        headers=auth_headers(user),
    )
    assert resp.status_code == 200
    # Bio should still be the original value (null = no-op)
    assert resp.json()["bio"] == "My original bio"
