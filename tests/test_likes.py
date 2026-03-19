"""tests/test_likes.py — Like / unlike endpoint tests."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers
from tests.factories import create_human, create_business, create_life_post, create_pulse_post


async def test_like_post_success(client: AsyncClient, db: AsyncSession) -> None:
    user = await create_human(db)
    author = await create_human(db)
    post = await create_life_post(db, author)
    await db.commit()

    resp = await client.post(f"/likes/{post.post_id}", headers=auth_headers(user))
    assert resp.status_code == 201
    assert resp.json()["liked"] is True
    assert resp.json()["post_id"] == str(post.post_id)


async def test_duplicate_like_returns_409(client: AsyncClient, db: AsyncSession) -> None:
    user = await create_human(db)
    author = await create_human(db)
    post = await create_life_post(db, author)
    await db.commit()

    await client.post(f"/likes/{post.post_id}", headers=auth_headers(user))
    resp = await client.post(f"/likes/{post.post_id}", headers=auth_headers(user))
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "ALREADY_LIKED"


async def test_unlike_post_success(client: AsyncClient, db: AsyncSession) -> None:
    user = await create_human(db)
    author = await create_human(db)
    post = await create_life_post(db, author)
    await db.commit()

    await client.post(f"/likes/{post.post_id}", headers=auth_headers(user))
    resp = await client.delete(f"/likes/{post.post_id}", headers=auth_headers(user))
    assert resp.status_code == 204


async def test_unlike_not_liked_returns_404(client: AsyncClient, db: AsyncSession) -> None:
    user = await create_human(db)
    author = await create_human(db)
    post = await create_life_post(db, author)
    await db.commit()

    resp = await client.delete(f"/likes/{post.post_id}", headers=auth_headers(user))
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "LIKE_NOT_FOUND"


async def test_like_pulse_post_is_blocked(client: AsyncClient, db: AsyncSession) -> None:
    """Pulse posts use upvotes/downvotes — likes are Life-post only."""
    user = await create_human(db)
    linked = await create_human(db)
    biz = await create_business(db, linked_human=linked)
    post = await create_pulse_post(db, biz)
    await db.commit()

    resp = await client.post(f"/likes/{post.post_id}", headers=auth_headers(user))
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "CANNOT_LIKE_PULSE_POST"
