"""tests/test_post_media.py — Multi-image post (carousel) tests."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers
from tests.factories import create_human, create_business, create_post


# ---------------------------------------------------------------------------
# POST creation with media
# ---------------------------------------------------------------------------

async def test_post_with_single_image(client: AsyncClient, db: AsyncSession) -> None:
    human = await create_human(db)
    await db.commit()
    resp = await client.post(
        "/posts",
        json={"content_text": "One pic", "media_urls": ["https://cdn.echo.app/img1.jpg"]},
        headers=auth_headers(human),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["media"]) == 1
    assert data["media"][0]["media_url"] == "https://cdn.echo.app/img1.jpg"
    assert data["media"][0]["position"] == 0


async def test_post_with_carousel(client: AsyncClient, db: AsyncSession) -> None:
    human = await create_human(db)
    await db.commit()
    urls = [f"https://cdn.echo.app/img{i}.jpg" for i in range(5)]
    resp = await client.post(
        "/posts",
        json={"content_text": "Five pics", "media_urls": urls},
        headers=auth_headers(human),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["media"]) == 5
    # Verify ordered by position
    positions = [item["position"] for item in data["media"]]
    assert positions == list(range(5))


async def test_post_media_url_order_preserved(client: AsyncClient, db: AsyncSession) -> None:
    """The position field must match the order the URLs were submitted in."""
    human = await create_human(db)
    await db.commit()
    urls = ["https://cdn.echo.app/a.jpg", "https://cdn.echo.app/b.jpg", "https://cdn.echo.app/c.jpg"]
    resp = await client.post(
        "/posts",
        json={"media_urls": urls},
        headers=auth_headers(human),
    )
    assert resp.status_code == 201
    media = resp.json()["media"]
    for i, item in enumerate(sorted(media, key=lambda x: x["position"])):
        assert item["media_url"] == urls[i]


async def test_post_text_only_has_empty_media(client: AsyncClient, db: AsyncSession) -> None:
    human = await create_human(db)
    await db.commit()
    resp = await client.post(
        "/posts",
        json={"content_text": "Text only post"},
        headers=auth_headers(human),
    )
    assert resp.status_code == 201
    assert resp.json()["media"] == []


async def test_post_requires_text_or_media(client: AsyncClient, db: AsyncSession) -> None:
    human = await create_human(db)
    await db.commit()
    resp = await client.post("/posts", json={}, headers=auth_headers(human))
    assert resp.status_code == 422


async def test_post_rejects_more_than_10_images(client: AsyncClient, db: AsyncSession) -> None:
    human = await create_human(db)
    await db.commit()
    urls = [f"https://cdn.echo.app/img{i}.jpg" for i in range(11)]
    resp = await client.post(
        "/posts",
        json={"media_urls": urls},
        headers=auth_headers(human),
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /posts/{id} returns media array
# ---------------------------------------------------------------------------

async def test_get_post_returns_media(client: AsyncClient, db: AsyncSession) -> None:
    human = await create_human(db)
    post = await create_post(
        db,
        human,
        media_urls=["https://cdn.echo.app/x.jpg", "https://cdn.echo.app/y.jpg"],
    )
    await db.commit()

    resp = await client.get(f"/posts/{post.post_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["media"]) == 2
    assert data["media"][0]["position"] == 0
    assert data["media"][1]["position"] == 1


# ---------------------------------------------------------------------------
# Feed responses include media array
# ---------------------------------------------------------------------------

async def test_life_feed_includes_media(client: AsyncClient, db: AsyncSession) -> None:
    from tests.factories import create_follow

    viewer = await create_human(db)
    poster = await create_human(db)
    await create_follow(db, follower=viewer, following=poster)
    await create_post(
        db,
        poster,
        media_urls=["https://cdn.echo.app/feed1.jpg", "https://cdn.echo.app/feed2.jpg"],
    )
    await db.commit()

    resp = await client.get("/feeds/life", headers=auth_headers(viewer))
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    # The post with media should have 2 media items
    post_with_media = next(
        (i for i in items if len(i.get("media", [])) == 2), None
    )
    assert post_with_media is not None


async def test_pulse_feed_includes_media(client: AsyncClient, db: AsyncSession) -> None:
    from tests.factories import create_business

    human = await create_human(db)
    biz = await create_business(db, linked_human=human)
    await create_post(
        db,
        biz,
        media_urls=["https://cdn.echo.app/pulse1.jpg"],
    )
    await db.commit()

    resp = await client.get("/feeds/pulse")
    assert resp.status_code == 200
    items = resp.json()["items"]
    post_with_media = next(
        (i for i in items if len(i.get("media", [])) == 1), None
    )
    assert post_with_media is not None


# ---------------------------------------------------------------------------
# Legacy: posts without media return empty media array
# ---------------------------------------------------------------------------

async def test_text_only_post_media_is_empty_in_feed(
    client: AsyncClient, db: AsyncSession
) -> None:
    from tests.factories import create_follow

    viewer = await create_human(db)
    poster = await create_human(db)
    await create_follow(db, follower=viewer, following=poster)
    await create_post(db, poster, content_text="No photos here")
    await db.commit()

    resp = await client.get("/feeds/life", headers=auth_headers(viewer))
    assert resp.status_code == 200
    items = resp.json()["items"]
    text_post = next(
        (i for i in items if i.get("content_text") == "No photos here"), None
    )
    assert text_post is not None
    assert text_post["media"] == []
