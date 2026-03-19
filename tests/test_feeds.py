"""tests/test_feeds.py — Life Feed and Pulse Feed endpoint tests."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers
from tests.factories import (
    create_business,
    create_echo,
    create_follow,
    create_human,
    create_life_post,
    create_pulse_post,
    create_vote,
)


# ------------------------------------------------------------------ #
# Life Feed
# ------------------------------------------------------------------ #

async def test_life_feed_empty_when_no_follows(client: AsyncClient, db: AsyncSession) -> None:
    viewer = await create_human(db)
    await db.commit()

    resp = await client.get("/feeds/life", headers=auth_headers(viewer))
    assert resp.status_code == 200
    assert resp.json()["items"] == []
    assert resp.json()["next_cursor"] is None


async def test_life_feed_shows_followed_human_posts(client: AsyncClient, db: AsyncSession) -> None:
    viewer = await create_human(db)
    author = await create_human(db)
    await create_follow(db, follower=viewer, following=author)
    post = await create_life_post(db, author, content_text="Hello from author")
    await db.commit()

    resp = await client.get("/feeds/life", headers=auth_headers(viewer))
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["content_text"] == "Hello from author"
    assert items[0]["is_pulse_post"] is False


async def test_life_feed_shows_echoed_pulse_posts(client: AsyncClient, db: AsyncSession) -> None:
    viewer = await create_human(db)
    echoer = await create_human(db)
    linked = await create_human(db)
    biz = await create_business(db, linked_human=linked)

    await create_follow(db, follower=viewer, following=echoer)
    pulse_post = await create_pulse_post(db, biz, content_text="Biz announcement")
    await create_echo(db, echoer=echoer, post=pulse_post)
    await db.commit()

    resp = await client.get("/feeds/life", headers=auth_headers(viewer))
    assert resp.status_code == 200
    items = resp.json()["items"]
    post_ids = [i["post_id"] for i in items]
    assert str(pulse_post.post_id) in post_ids


async def test_life_feed_requires_auth(client: AsyncClient, db: AsyncSession) -> None:
    resp = await client.get("/feeds/life")
    assert resp.status_code == 401


# ------------------------------------------------------------------ #
# Pulse Feed
# ------------------------------------------------------------------ #

async def test_pulse_feed_public_no_auth(client: AsyncClient, db: AsyncSession) -> None:
    linked = await create_human(db)
    biz = await create_business(db, linked_human=linked)
    await create_pulse_post(db, biz, content_text="Pulse post 1")
    await db.commit()

    resp = await client.get("/feeds/pulse")
    assert resp.status_code == 200
    assert "items" in resp.json()


async def test_pulse_feed_excludes_life_posts(client: AsyncClient, db: AsyncSession) -> None:
    author = await create_human(db)
    await create_life_post(db, author, content_text="This is a life post")
    linked = await create_human(db)
    biz = await create_business(db, linked_human=linked)
    pulse = await create_pulse_post(db, biz, content_text="Pulse only")
    await db.commit()

    resp = await client.get("/feeds/pulse")
    assert resp.status_code == 200
    items = resp.json()["items"]
    post_ids = [i["post_id"] for i in items]
    assert str(pulse.post_id) in post_ids
    # Life posts must NOT appear in Pulse feed
    for item in items:
        assert item["is_pulse_post"] is True


async def test_pulse_feed_sorted_by_net_score(client: AsyncClient, db: AsyncSession) -> None:
    voter = await create_human(db)
    linked = await create_human(db)
    biz = await create_business(db, linked_human=linked)
    low_score_post = await create_pulse_post(db, biz, content_text="Low score")
    high_score_post = await create_pulse_post(db, biz, content_text="High score")
    # Give high_score_post 2 upvotes
    voter2 = await create_human(db)
    await create_vote(db, voter, high_score_post, vote_value=1)
    await create_vote(db, voter2, high_score_post, vote_value=1)
    await db.commit()

    resp = await client.get("/feeds/pulse")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 2
    # High score post should appear first
    assert items[0]["post_id"] == str(high_score_post.post_id)
