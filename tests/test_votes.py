"""tests/test_votes.py — Vote endpoint tests (Pulse Feed ranking signal)."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers
from tests.factories import create_human, create_business, create_pulse_post, create_life_post


async def test_upvote_pulse_post(client: AsyncClient, db: AsyncSession) -> None:
    user = await create_human(db)
    linked = await create_human(db)
    biz = await create_business(db, linked_human=linked)
    post = await create_pulse_post(db, biz)
    await db.commit()

    resp = await client.post(
        "/votes",
        json={"post_id": str(post.post_id), "vote_value": 1},
        headers=auth_headers(user),
    )
    assert resp.status_code == 201
    assert resp.json()["vote_value"] == 1
    assert resp.json()["post_id"] == str(post.post_id)


async def test_downvote_pulse_post(client: AsyncClient, db: AsyncSession) -> None:
    user = await create_human(db)
    linked = await create_human(db)
    biz = await create_business(db, linked_human=linked)
    post = await create_pulse_post(db, biz)
    await db.commit()

    resp = await client.post(
        "/votes",
        json={"post_id": str(post.post_id), "vote_value": -1},
        headers=auth_headers(user),
    )
    assert resp.status_code == 201
    assert resp.json()["vote_value"] == -1


async def test_change_vote_updates_value(client: AsyncClient, db: AsyncSession) -> None:
    """Voting twice on the same post updates the existing vote (no duplicate)."""
    user = await create_human(db)
    linked = await create_human(db)
    biz = await create_business(db, linked_human=linked)
    post = await create_pulse_post(db, biz)
    await db.commit()

    await client.post(
        "/votes",
        json={"post_id": str(post.post_id), "vote_value": 1},
        headers=auth_headers(user),
    )
    resp = await client.post(
        "/votes",
        json={"post_id": str(post.post_id), "vote_value": -1},
        headers=auth_headers(user),
    )
    assert resp.status_code == 201
    assert resp.json()["vote_value"] == -1


async def test_remove_vote(client: AsyncClient, db: AsyncSession) -> None:
    user = await create_human(db)
    linked = await create_human(db)
    biz = await create_business(db, linked_human=linked)
    post = await create_pulse_post(db, biz)
    await db.commit()

    await client.post(
        "/votes",
        json={"post_id": str(post.post_id), "vote_value": 1},
        headers=auth_headers(user),
    )
    resp = await client.delete(f"/votes/{post.post_id}", headers=auth_headers(user))
    assert resp.status_code == 204


async def test_remove_vote_not_found_returns_404(client: AsyncClient, db: AsyncSession) -> None:
    user = await create_human(db)
    linked = await create_human(db)
    biz = await create_business(db, linked_human=linked)
    post = await create_pulse_post(db, biz)
    await db.commit()

    resp = await client.delete(f"/votes/{post.post_id}", headers=auth_headers(user))
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "VOTE_NOT_FOUND"


async def test_cannot_vote_on_life_post(client: AsyncClient, db: AsyncSession) -> None:
    """Votes are only for Pulse posts."""
    user = await create_human(db)
    author = await create_human(db)
    life_post = await create_life_post(db, author)
    await db.commit()

    resp = await client.post(
        "/votes",
        json={"post_id": str(life_post.post_id), "vote_value": 1},
        headers=auth_headers(user),
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "CANNOT_VOTE_LIFE_POST"
