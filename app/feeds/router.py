"""
app/feeds/router.py — Feed retrieval endpoints.

GET /feeds/life   — authenticated; returns the viewer's Life Feed
GET /feeds/pulse  — public; returns the global Pulse Feed
"""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, get_current_user_optional
from app.database import get_async_db
from app.feeds.schemas import FeedResponse
from app.feeds.service import get_life_feed, get_pulse_feed
from app.models.user import User

router = APIRouter(prefix="/feeds", tags=["feeds"])


@router.get("/life", response_model=FeedResponse)
async def life_feed(
    cursor: str | None = Query(default=None, description="ISO datetime cursor from previous page"),
    limit: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> FeedResponse:
    """
    Life Feed — strictly chronological.
    Shows original posts from followed Humans + Echoed Pulse posts (filtered by mute_echoes).
    Requires authentication (must know who the viewer follows).
    """
    parsed_cursor: datetime | None = None
    if cursor:
        try:
            parsed_cursor = datetime.fromisoformat(cursor)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "INVALID_CURSOR", "message": "cursor must be an ISO datetime string."},
            )

    return await get_life_feed(current_user, db, cursor=parsed_cursor, limit=limit)


@router.get("/pulse", response_model=FeedResponse)
async def pulse_feed(
    cursor: str | None = Query(default=None, description="JSON cursor {score, ts} from previous page"),
    limit: int = Query(default=20, ge=1, le=50),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_async_db),
) -> FeedResponse:
    """
    Pulse Feed — sorted by community net-score (upvotes − downvotes).
    Public endpoint — no authentication required.
    When authenticated, response includes current_user_vote and is_echoed_by_current_user per post.
    """
    cursor_score: int | None = None
    cursor_ts: datetime | None = None

    if cursor:
        try:
            data = json.loads(cursor)
            cursor_score = int(data["score"])
            cursor_ts = datetime.fromisoformat(data["ts"])
        except (ValueError, KeyError, json.JSONDecodeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "INVALID_CURSOR", "message": "Invalid pagination cursor."},
            )

    return await get_pulse_feed(
        db,
        viewer=current_user,
        cursor_score=cursor_score,
        cursor_ts=cursor_ts,
        limit=limit,
    )
