"""
app/feeds/service.py — Life Feed and Pulse Feed query logic.

This is the core product logic. Both functions are carefully guarded:

Life Feed invariants (RULES.md):
  1. Sort: strictly chronological (created_at DESC or echo.created_at DESC)
  2. Content: Human posts from followed users + Echoed Pulse posts from followed Humans
  3. CRITICAL: mute_echoes filter applied on EVERY call — never skipped
  4. Business/Meme/Info posts ONLY appear via the echoes table

Pulse Feed invariants:
  1. Sort: net_score DESC, created_at DESC (no other ranking signals)
  2. Content: only is_pulse_post = True posts
  3. net_score = SUM(vote_value) per post — internal only, not shown on profiles
"""

import json
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.feeds.schemas import FeedResponse, LifeFeedItem, PulseFeedItem
from app.models.echo import Echo
from app.models.follow import Follow
from app.models.like import Like
from app.models.mute_echo import MuteEcho
from app.models.post import Post
from app.models.user import AccountType, User
from app.models.vote import Vote

logger = logging.getLogger(__name__)

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 50


async def get_life_feed(
    viewer: User,
    db: AsyncSession,
    cursor: datetime | None = None,
    limit: int = _DEFAULT_LIMIT,
) -> FeedResponse:
    """
    Life Feed: strictly chronological mix of original Human posts
    and Echoed Pulse posts from followed Human users.

    CRITICAL: mute_echoes filter is applied on every call.
    Skipping it is a CRITICAL bug (RULES.md invariant 5).
    """
    limit = min(limit, _MAX_LIMIT)
    viewer_id = viewer.user_id

    # Step 1: Collect who the viewer follows
    follows_q = await db.execute(
        select(Follow.following_id).where(Follow.follower_id == viewer_id)
    )
    followed_ids: list[uuid.UUID] = [row[0] for row in follows_q.fetchall()]

    if not followed_ids:
        return FeedResponse(items=[], next_cursor=None)

    # Step 2: Collect muted users (whose Echoes the viewer suppresses)
    # CRITICAL: This must ALWAYS be fetched and applied.
    mutes_q = await db.execute(
        select(MuteEcho.muted_user_id).where(MuteEcho.user_id == viewer_id)
    )
    muted_ids: set[uuid.UUID] = {row[0] for row in mutes_q.fetchall()}

    # Step 3a: Original Life posts from followed Human accounts
    # Only Human accounts produce Life posts (is_pulse_post = False)
    original_posts_q = (
        select(
            Post.post_id,
            Post.author_id,
            Post.content_text,
            Post.media_url,
            Post.is_pulse_post,
            Post.created_at.label("sort_ts"),
            User.username.label("author_username"),
            func.count(Like.post_id).label("like_count"),
            text("NULL::text").label("echoed_by_username"),
            text("NULL::timestamptz").label("echoed_at"),
        )
        .join(User, Post.author_id == User.user_id)
        .outerjoin(Like, Like.post_id == Post.post_id)
        .where(
            Post.author_id.in_(followed_ids),
            Post.is_pulse_post.is_(False),
        )
        .group_by(
            Post.post_id, Post.author_id, Post.content_text,
            Post.media_url, Post.is_pulse_post, Post.created_at,
            User.username,
        )
    )

    # Step 3b: Echoed Pulse posts from followed Humans (not muted)
    # The sort timestamp is echo.created_at, NOT post.created_at
    # (the post appears in the feed at the time the Human vouched for it)
    echoed_posts_q = (
        select(
            Post.post_id,
            Post.author_id,
            Post.content_text,
            Post.media_url,
            Post.is_pulse_post,
            Echo.created_at.label("sort_ts"),  # <-- echo timestamp, not post timestamp
            User.username.label("author_username"),
            text("0").label("like_count"),
            EchoUser.username.label("echoed_by_username"),
            Echo.created_at.label("echoed_at"),
        )
        .join(User, Post.author_id == User.user_id)
        .join(Echo, Echo.post_id == Post.post_id)
        .join(EchoUser := User.__class__, Echo.echoer_id == text("echoer.user_id"))
        .where(
            Echo.echoer_id.in_(followed_ids),
            Post.is_pulse_post.is_(True),
        )
    )

    # Simpler approach using aliased
    from sqlalchemy.orm import aliased
    EchoUser = aliased(User, name="echo_user")

    echoed_posts_q = (
        select(
            Post.post_id,
            Post.author_id,
            Post.content_text,
            Post.media_url,
            Post.is_pulse_post,
            Echo.created_at.label("sort_ts"),
            User.username.label("author_username"),
            text("0").label("like_count"),
            EchoUser.username.label("echoed_by_username"),
            Echo.created_at.label("echoed_at"),
        )
        .join(User, Post.author_id == User.user_id)
        .join(Echo, Echo.post_id == Post.post_id)
        .join(EchoUser, Echo.echoer_id == EchoUser.user_id)
        .where(
            Echo.echoer_id.in_(followed_ids),
            Post.is_pulse_post.is_(True),
            # CRITICAL: exclude Echoes from muted users
            Echo.echoer_id.not_in(muted_ids) if muted_ids else text("true"),
        )
    )

    # Step 4: UNION and apply cursor + sort
    combined = original_posts_q.union_all(echoed_posts_q).subquery()

    final_q = select(combined)
    if cursor:
        final_q = final_q.where(combined.c.sort_ts < cursor)
    final_q = final_q.order_by(combined.c.sort_ts.desc()).limit(limit + 1)

    result = await db.execute(final_q)
    rows = result.fetchall()

    has_next = len(rows) > limit
    rows = rows[:limit]

    items = [
        LifeFeedItem(
            post_id=row.post_id,
            author_id=row.author_id,
            author_username=row.author_username,
            content_text=row.content_text,
            media_url=row.media_url,
            is_pulse_post=row.is_pulse_post,
            created_at=row.sort_ts,
            like_count=row.like_count or 0,
            echoed_by_username=row.echoed_by_username,
            echoed_at=row.echoed_at,
        )
        for row in rows
    ]

    next_cursor = rows[-1].sort_ts.isoformat() if has_next and rows else None
    return FeedResponse(items=items, next_cursor=next_cursor)


async def get_pulse_feed(
    db: AsyncSession,
    cursor_score: int | None = None,
    cursor_ts: datetime | None = None,
    limit: int = _DEFAULT_LIMIT,
) -> FeedResponse:
    """
    Pulse Feed: Popularity-based global discovery feed.
    Sorted by net_score DESC, created_at DESC.
    No algorithmic influence — community votes only (Rule 1).
    net_score is internal; not shown on user profiles.
    """
    limit = min(limit, _MAX_LIMIT)

    net_score = func.coalesce(func.sum(Vote.vote_value), 0).label("net_score")

    q = (
        select(
            Post.post_id,
            Post.author_id,
            Post.content_text,
            Post.media_url,
            Post.is_pulse_post,
            Post.created_at,
            User.username.label("author_username"),
            net_score,
        )
        .join(User, Post.author_id == User.user_id)
        .outerjoin(Vote, Vote.post_id == Post.post_id)
        .where(Post.is_pulse_post.is_(True))
        .group_by(
            Post.post_id, Post.author_id, Post.content_text,
            Post.media_url, Post.is_pulse_post, Post.created_at,
            User.username,
        )
    )

    # Keyset pagination using composite (net_score, created_at) cursor
    if cursor_score is not None and cursor_ts is not None:
        q = q.where(
            (net_score < cursor_score)
            | ((net_score == cursor_score) & (Post.created_at < cursor_ts))
        )

    q = q.order_by(net_score.desc(), Post.created_at.desc()).limit(limit + 1)

    result = await db.execute(q)
    rows = result.fetchall()

    has_next = len(rows) > limit
    rows = rows[:limit]

    items = [
        PulseFeedItem(
            post_id=row.post_id,
            author_id=row.author_id,
            author_username=row.author_username,
            content_text=row.content_text,
            media_url=row.media_url,
            is_pulse_post=row.is_pulse_post,
            created_at=row.created_at,
            net_score=row.net_score,
        )
        for row in rows
    ]

    next_cursor = None
    if has_next and rows:
        last = rows[-1]
        next_cursor = json.dumps({"score": last.net_score, "ts": last.created_at.isoformat()})

    return FeedResponse(items=items, next_cursor=next_cursor)
