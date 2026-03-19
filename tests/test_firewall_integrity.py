"""
tests/test_firewall_integrity.py — Rule 7 mandatory pre-release tests.

These five tests MUST pass before any backend deployment.
A failure here indicates a CRITICAL bug.

1. Firewall test:   Business post NEVER appears directly in Life Feed
2. Verification:    Unverified users get 403 on ALL write endpoints
3. Sort test:       Life Feed is strictly chronological (created_at DESC)
4. Echo test:       Human-echoed Pulse post appears in follower's Life Feed
5. Mute test:       Muting a user's echoes removes their echoed posts
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers
from tests.factories import (
    create_business,
    create_echo,
    create_follow,
    create_human,
    create_mute,
    create_pulse_post,
    create_unverified_user,
)


# ------------------------------------------------------------------ #
# Test 1: Human Firewall — Business post blocked from Life Feed
# ------------------------------------------------------------------ #

async def test_business_post_does_not_appear_in_life_feed(
    client: AsyncClient, db: AsyncSession
) -> None:
    """
    FIREWALL TEST (Rule 7.1):
    A Business account posts content. A Human follower's Life Feed
    must NOT contain that Business post directly.
    """
    human = await create_human(db)
    linked_human = await create_human(db)
    business = await create_business(db, linked_human=linked_human)

    # Human follows the Business account
    await create_follow(db, follower=human, following=business)
    await db.commit()

    # Business posts a Pulse post
    resp = await client.post(
        "/posts",
        json={"content_text": "Buy our product!"},
        headers=auth_headers(business),
    )
    assert resp.status_code == 201
    post_data = resp.json()
    assert post_data["is_pulse_post"] is True

    # Human checks their Life Feed — business post must NOT appear
    feed_resp = await client.get("/feeds/life", headers=auth_headers(human))
    assert feed_resp.status_code == 200
    post_ids = [item["post_id"] for item in feed_resp.json()["items"]]
    assert post_data["post_id"] not in post_ids, (
        "CRITICAL BUG: Business post appeared directly in Life Feed "
        "without a Human Echo. Human Firewall is broken."
    )


# ------------------------------------------------------------------ #
# Test 2: Age verification gate on ALL write endpoints
# ------------------------------------------------------------------ #

WRITE_ENDPOINTS = [
    ("POST", "/posts", {"content_text": "hello"}),
    ("POST", "/echoes", {"post_id": "00000000-0000-0000-0000-000000000000"}),
    ("POST", "/follows", {"following_id": "00000000-0000-0000-0000-000000000000"}),
    ("POST", "/likes/00000000-0000-0000-0000-000000000000", {}),
    ("POST", "/votes", {"post_id": "00000000-0000-0000-0000-000000000000", "vote_value": 1}),
    ("POST", "/mute-echoes/00000000-0000-0000-0000-000000000000", {}),
    ("POST", "/media/presigned-url", {"content_type": "image/jpeg", "file_size_bytes": 1000}),
]


@pytest.mark.parametrize("method,path,body", WRITE_ENDPOINTS)
async def test_unverified_user_blocked_on_write_endpoints(
    method: str, path: str, body: dict, client: AsyncClient, db: AsyncSession
) -> None:
    """
    VERIFICATION TEST (Rule 7.2):
    An unverified user (is_verified_human=False) must receive 403
    on every write endpoint.
    """
    unverified = await create_unverified_user(db)
    await db.commit()

    resp = await client.request(
        method, path, json=body, headers=auth_headers(unverified)
    )
    assert resp.status_code == 403, (
        f"CRITICAL BUG: Unverified user was NOT blocked on {method} {path}. "
        f"Got status {resp.status_code}. "
        f"Texas SB 2420 compliance is broken."
    )
    assert resp.json()["detail"]["code"] == "AGE_VERIFICATION_REQUIRED"


# ------------------------------------------------------------------ #
# Test 3: Life Feed is strictly chronological
# ------------------------------------------------------------------ #

async def test_life_feed_is_strictly_chronological(
    client: AsyncClient, db: AsyncSession
) -> None:
    """
    SORT TEST (Rule 7.3):
    Life Feed posts must be ordered by created_at DESC with no reordering.
    """
    viewer = await create_human(db)
    author = await create_human(db)
    await create_follow(db, follower=viewer, following=author)

    # Create posts with explicit, varied timestamps
    from app.models.post import Post
    now = datetime.now(UTC)
    for i in range(5):
        post = Post(
            author_id=author.user_id,
            content_text=f"Post {i}",
            is_pulse_post=False,
            created_at=now - timedelta(minutes=i * 10),  # older as i increases
        )
        db.add(post)
    await db.commit()

    feed_resp = await client.get("/feeds/life", headers=auth_headers(viewer))
    assert feed_resp.status_code == 200
    items = feed_resp.json()["items"]
    assert len(items) >= 5

    timestamps = [item["created_at"] for item in items]
    assert timestamps == sorted(timestamps, reverse=True), (
        "CRITICAL BUG: Life Feed is not sorted strictly chronologically. "
        "An algorithmic sort may have been introduced."
    )


# ------------------------------------------------------------------ #
# Test 4: Echo makes Pulse post appear in follower's Life Feed
# ------------------------------------------------------------------ #

async def test_echoed_pulse_post_appears_in_life_feed(
    client: AsyncClient, db: AsyncSession
) -> None:
    """
    ECHO TEST (Rule 7.4):
    When a Human echoes a Pulse post, that post must appear in
    the Human's followers' Life Feeds.
    """
    viewer = await create_human(db)
    echoer = await create_human(db)
    linked_human = await create_human(db)
    business = await create_business(db, linked_human=linked_human)

    # Viewer follows the echoer
    await create_follow(db, follower=viewer, following=echoer)

    # Business publishes a Pulse post
    pulse_post = await create_pulse_post(db, business, content_text="Big sale!")
    await db.commit()

    # Echoer echoes the Pulse post into their followers' Life Feeds
    echo_resp = await client.post(
        "/echoes",
        json={"post_id": str(pulse_post.post_id)},
        headers=auth_headers(echoer),
    )
    assert echo_resp.status_code == 201

    # Viewer checks their Life Feed — echoed post must appear
    feed_resp = await client.get("/feeds/life", headers=auth_headers(viewer))
    assert feed_resp.status_code == 200
    post_ids = [item["post_id"] for item in feed_resp.json()["items"]]
    assert str(pulse_post.post_id) in post_ids, (
        "BUG: Human-echoed Pulse post did not appear in follower's Life Feed. "
        "Echo bridge is broken."
    )


# ------------------------------------------------------------------ #
# Test 5: Muting echoes hides echoed posts but keeps original posts
# ------------------------------------------------------------------ #

async def test_muting_echoes_hides_echoed_posts_keeps_originals(
    client: AsyncClient, db: AsyncSession
) -> None:
    """
    MUTE TEST (Rule 7.5):
    After muting a user's echoes, their echoed Pulse posts disappear
    from the viewer's Life Feed. Their original Life posts remain visible.
    """
    viewer = await create_human(db)
    echoer = await create_human(db)
    linked_human = await create_human(db)
    business = await create_business(db, linked_human=linked_human)

    await create_follow(db, follower=viewer, following=echoer)

    # Echoer posts an original Life post
    from app.models.post import Post as PostModel
    original_post = PostModel(
        author_id=echoer.user_id,
        content_text="My original life post",
        is_pulse_post=False,
    )
    db.add(original_post)

    # Business post that gets echoed
    pulse_post = await create_pulse_post(db, business, content_text="Echoed content")
    echo = await create_echo(db, echoer=echoer, post=pulse_post)
    await db.commit()

    # Before mute: both should be visible
    feed_before = await client.get("/feeds/life", headers=auth_headers(viewer))
    items_before = feed_before.json()["items"]
    post_ids_before = [item["post_id"] for item in items_before]
    assert str(pulse_post.post_id) in post_ids_before, "Echo should appear before mute"

    # Apply mute
    mute_resp = await client.post(
        f"/mute-echoes/{echoer.user_id}",
        headers=auth_headers(viewer),
    )
    assert mute_resp.status_code == 201

    # After mute: echoed post gone, original life post still visible
    feed_after = await client.get("/feeds/life", headers=auth_headers(viewer))
    items_after = feed_after.json()["items"]
    post_ids_after = [item["post_id"] for item in items_after]

    assert str(pulse_post.post_id) not in post_ids_after, (
        "CRITICAL BUG: Muted echo still appears in Life Feed. "
        "mute_echoes filter is broken."
    )
    assert str(original_post.post_id) in post_ids_after, (
        "BUG: Original Life post disappeared after muting echoes. "
        "Mute should only suppress echoes, not original posts."
    )
