"""tests/test_comments.py — Comment system tests.

Covers:
  POST /posts/{post_id}/comments     — create comment or reply
  GET  /posts/{post_id}/comments     — list top-level comments (public)
  GET  /comments/{comment_id}/replies — list replies (public)
  DELETE /comments/{comment_id}       — delete own comment (auth required)
"""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers
from tests.factories import create_comment, create_human, create_life_post


# ------------------------------------------------------------------ #
# POST /posts/{post_id}/comments — create comment or reply
# ------------------------------------------------------------------ #


async def test_create_comment_success(
    client: AsyncClient, db: AsyncSession
) -> None:
    """201 with correct fields when creating a top-level comment."""
    author = await create_human(db)
    post = await create_life_post(db, author)
    commenter = await create_human(db)
    await db.commit()

    resp = await client.post(
        f"/posts/{post.post_id}/comments",
        json={"content_text": "Great post!"},
        headers=auth_headers(commenter),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["content_text"] == "Great post!"
    assert data["author_username"] == commenter.username
    assert data["parent_id"] is None
    assert data["reply_count"] == 0
    assert "comment_id" in data
    assert "created_at" in data


async def test_create_comment_requires_auth(
    client: AsyncClient, db: AsyncSession
) -> None:
    """401 when unauthenticated."""
    author = await create_human(db)
    post = await create_life_post(db, author)
    await db.commit()

    resp = await client.post(
        f"/posts/{post.post_id}/comments",
        json={"content_text": "Sneaky comment"},
    )
    assert resp.status_code == 401


async def test_create_comment_on_nonexistent_post_404(
    client: AsyncClient, db: AsyncSession
) -> None:
    """404 POST_NOT_FOUND when post doesn't exist."""
    user = await create_human(db)
    await db.commit()

    fake_post_id = uuid.uuid4()
    resp = await client.post(
        f"/posts/{fake_post_id}/comments",
        json={"content_text": "Orphan comment"},
        headers=auth_headers(user),
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "POST_NOT_FOUND"


async def test_create_reply_success(
    client: AsyncClient, db: AsyncSession
) -> None:
    """201 with parent_id set when creating a reply."""
    author = await create_human(db)
    post = await create_life_post(db, author)
    commenter = await create_human(db)
    replier = await create_human(db)
    await db.commit()

    # Create top-level comment via factory (already tested above)
    parent = await create_comment(db, commenter, post, content_text="Original comment")
    await db.commit()

    resp = await client.post(
        f"/posts/{post.post_id}/comments",
        json={"content_text": "Reply here!", "parent_id": str(parent.comment_id)},
        headers=auth_headers(replier),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["parent_id"] == str(parent.comment_id)
    assert data["content_text"] == "Reply here!"


async def test_create_reply_wrong_post_404(
    client: AsyncClient, db: AsyncSession
) -> None:
    """404 PARENT_COMMENT_NOT_FOUND when parent_id belongs to a different post."""
    author = await create_human(db)
    post1 = await create_life_post(db, author, content_text="Post 1")
    post2 = await create_life_post(db, author, content_text="Post 2")
    commenter = await create_human(db)
    await db.commit()

    # Comment on post1
    comment = await create_comment(db, commenter, post1)
    await db.commit()

    # Try to reply on post2 using post1's comment as parent
    replier = await create_human(db)
    await db.commit()

    resp = await client.post(
        f"/posts/{post2.post_id}/comments",
        json={
            "content_text": "Wrong post reply",
            "parent_id": str(comment.comment_id),
        },
        headers=auth_headers(replier),
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "PARENT_COMMENT_NOT_FOUND"


# ------------------------------------------------------------------ #
# GET /posts/{post_id}/comments — list top-level comments (public)
# ------------------------------------------------------------------ #


async def test_get_comments_empty(
    client: AsyncClient, db: AsyncSession
) -> None:
    """200 with empty list when post has no comments."""
    author = await create_human(db)
    post = await create_life_post(db, author)
    await db.commit()

    resp = await client.get(f"/posts/{post.post_id}/comments")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_comments_shows_top_level_only(
    client: AsyncClient, db: AsyncSession
) -> None:
    """
    Top-level GET only returns parent_id=NULL comments.
    The one top-level comment should have reply_count=1 (from the reply).
    The reply itself should NOT appear in the list.
    """
    author = await create_human(db)
    post = await create_life_post(db, author)
    commenter = await create_human(db)
    replier = await create_human(db)
    await db.commit()

    top = await create_comment(db, commenter, post, content_text="Top comment")
    await create_comment(db, replier, post, content_text="Reply", parent_id=top.comment_id)
    await db.commit()

    resp = await client.get(f"/posts/{post.post_id}/comments")
    assert resp.status_code == 200
    items = resp.json()

    # Only the top-level comment is returned
    assert len(items) == 1
    assert items[0]["comment_id"] == str(top.comment_id)
    assert items[0]["parent_id"] is None
    assert items[0]["reply_count"] == 1


# ------------------------------------------------------------------ #
# GET /comments/{comment_id}/replies — list replies (public)
# ------------------------------------------------------------------ #


async def test_get_replies(
    client: AsyncClient, db: AsyncSession
) -> None:
    """200 with correct reply list for a parent comment."""
    author = await create_human(db)
    post = await create_life_post(db, author)
    commenter = await create_human(db)
    replier1 = await create_human(db)
    replier2 = await create_human(db)
    await db.commit()

    parent = await create_comment(db, commenter, post, content_text="Parent")
    r1 = await create_comment(db, replier1, post, content_text="Reply 1", parent_id=parent.comment_id)
    r2 = await create_comment(db, replier2, post, content_text="Reply 2", parent_id=parent.comment_id)
    await db.commit()

    resp = await client.get(f"/comments/{parent.comment_id}/replies")
    assert resp.status_code == 200
    items = resp.json()

    assert len(items) == 2
    ids = {item["comment_id"] for item in items}
    assert str(r1.comment_id) in ids
    assert str(r2.comment_id) in ids
    # All replies reference the parent
    for item in items:
        assert item["parent_id"] == str(parent.comment_id)


async def test_get_replies_nonexistent_comment_404(
    client: AsyncClient, db: AsyncSession
) -> None:
    """404 COMMENT_NOT_FOUND when comment doesn't exist."""
    await db.commit()

    resp = await client.get(f"/comments/{uuid.uuid4()}/replies")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "COMMENT_NOT_FOUND"


# ------------------------------------------------------------------ #
# DELETE /comments/{comment_id} — delete own comment
# ------------------------------------------------------------------ #


async def test_delete_own_comment_success(
    client: AsyncClient, db: AsyncSession
) -> None:
    """204 when deleting your own comment."""
    author = await create_human(db)
    post = await create_life_post(db, author)
    commenter = await create_human(db)
    await db.commit()

    comment = await create_comment(db, commenter, post)
    await db.commit()

    resp = await client.delete(
        f"/comments/{comment.comment_id}",
        headers=auth_headers(commenter),
    )
    assert resp.status_code == 204

    # Comment gone — replies endpoint should 404
    get_resp = await client.get(f"/comments/{comment.comment_id}/replies")
    assert get_resp.status_code == 404


async def test_delete_others_comment_403(
    client: AsyncClient, db: AsyncSession
) -> None:
    """403 FORBIDDEN when attempting to delete someone else's comment."""
    author = await create_human(db)
    post = await create_life_post(db, author)
    commenter = await create_human(db)
    other = await create_human(db)
    await db.commit()

    comment = await create_comment(db, commenter, post)
    await db.commit()

    resp = await client.delete(
        f"/comments/{comment.comment_id}",
        headers=auth_headers(other),
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "FORBIDDEN"


async def test_delete_nonexistent_comment_404(
    client: AsyncClient, db: AsyncSession
) -> None:
    """404 COMMENT_NOT_FOUND when comment doesn't exist."""
    user = await create_human(db)
    await db.commit()

    resp = await client.delete(
        f"/comments/{uuid.uuid4()}",
        headers=auth_headers(user),
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "COMMENT_NOT_FOUND"


# ------------------------------------------------------------------ #
# Mention parsing — verify content preserved and no crash
# ------------------------------------------------------------------ #


async def test_mention_parsed_from_content(
    client: AsyncClient, db: AsyncSession
) -> None:
    """201 with full content when comment contains @mentions (no crash)."""
    author = await create_human(db)
    post = await create_life_post(db, author)
    commenter = await create_human(db)
    await db.commit()

    resp = await client.post(
        f"/posts/{post.post_id}/comments",
        json={"content_text": f"Hey @{author.username} check this out!"},
        headers=auth_headers(commenter),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert author.username in data["content_text"]
