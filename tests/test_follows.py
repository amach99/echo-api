"""tests/test_follows.py — Follow / unfollow endpoint tests."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers
from tests.factories import create_human


async def test_follow_user_success(client: AsyncClient, db: AsyncSession) -> None:
    follower = await create_human(db)
    target = await create_human(db)
    await db.commit()

    resp = await client.post(
        "/follows",
        json={"following_id": str(target.user_id)},
        headers=auth_headers(follower),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["follower_id"] == str(follower.user_id)
    assert data["following_id"] == str(target.user_id)


async def test_duplicate_follow_returns_409(client: AsyncClient, db: AsyncSession) -> None:
    follower = await create_human(db)
    target = await create_human(db)
    await db.commit()

    await client.post(
        "/follows",
        json={"following_id": str(target.user_id)},
        headers=auth_headers(follower),
    )
    resp = await client.post(
        "/follows",
        json={"following_id": str(target.user_id)},
        headers=auth_headers(follower),
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "ALREADY_FOLLOWING"


async def test_unfollow_user_success(client: AsyncClient, db: AsyncSession) -> None:
    follower = await create_human(db)
    target = await create_human(db)
    await db.commit()

    await client.post(
        "/follows",
        json={"following_id": str(target.user_id)},
        headers=auth_headers(follower),
    )
    resp = await client.delete(
        f"/follows/{target.user_id}",
        headers=auth_headers(follower),
    )
    assert resp.status_code == 204


async def test_unfollow_non_existent_returns_404(client: AsyncClient, db: AsyncSession) -> None:
    follower = await create_human(db)
    target = await create_human(db)
    await db.commit()

    resp = await client.delete(
        f"/follows/{target.user_id}",
        headers=auth_headers(follower),
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "FOLLOW_NOT_FOUND"
