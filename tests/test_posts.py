"""tests/test_posts.py — Post creation and routing tests."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers
from tests.factories import create_business, create_human, create_unverified_user


async def test_human_post_routes_to_life_feed(client: AsyncClient, db: AsyncSession) -> None:
    human = await create_human(db)
    await db.commit()
    resp = await client.post("/posts", json={"content_text": "Hello life!"},
                             headers=auth_headers(human))
    assert resp.status_code == 201
    assert resp.json()["is_pulse_post"] is False


async def test_business_post_routes_to_pulse_feed(client: AsyncClient, db: AsyncSession) -> None:
    linked = await create_human(db)
    biz = await create_business(db, linked_human=linked)
    await db.commit()
    resp = await client.post("/posts", json={"content_text": "Buy now!"},
                             headers=auth_headers(biz))
    assert resp.status_code == 201
    assert resp.json()["is_pulse_post"] is True


async def test_client_cannot_set_is_pulse_post(client: AsyncClient, db: AsyncSession) -> None:
    """is_pulse_post is NOT in PostCreate schema — server ignores/rejects it."""
    human = await create_human(db)
    await db.commit()
    # Even if client sends is_pulse_post=True, a Human's post must be is_pulse_post=False
    resp = await client.post("/posts",
                             json={"content_text": "Hello", "is_pulse_post": True},
                             headers=auth_headers(human))
    assert resp.status_code == 201
    assert resp.json()["is_pulse_post"] is False


async def test_empty_post_rejected(client: AsyncClient, db: AsyncSession) -> None:
    human = await create_human(db)
    await db.commit()
    resp = await client.post("/posts", json={}, headers=auth_headers(human))
    assert resp.status_code == 422


async def test_unverified_user_cannot_post(client: AsyncClient, db: AsyncSession) -> None:
    unverified = await create_unverified_user(db)
    await db.commit()
    resp = await client.post("/posts", json={"content_text": "Hello"},
                             headers=auth_headers(unverified))
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "AGE_VERIFICATION_REQUIRED"
