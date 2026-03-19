"""
app/comments/router.py — Comment endpoints.

Two routers:
  post_comments_router — prefix /posts/{post_id}/comments
    POST  ""           create comment or reply (auth + age verified)
    GET   ""           list top-level comments (public)

  comments_router — prefix /comments
    GET   /{comment_id}/replies  list replies (public)
    DELETE /{comment_id}         delete own comment (auth required)

POST has require_age_verified at endpoint level (not router level) so the
public GET on the same prefix doesn't require authentication.
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.comments.schemas import CommentResponse, CreateCommentRequest
from app.comments.service import (
    create_comment,
    delete_comment,
    list_comment_replies,
    list_post_comments,
)
from app.database import get_async_db
from app.middleware.age_verification import require_age_verified
from app.models.post import Post
from app.models.user import User
from app.notifications.adapter import PushAdapter, get_push_adapter
from app.notifications.service import (
    dispatch_push,
    extract_mentions,
    get_tokens_for_comment_author,
    get_tokens_for_user,
    get_tokens_for_usernames,
)

post_comments_router = APIRouter(
    prefix="/posts/{post_id}/comments",
    tags=["comments"],
)

comments_router = APIRouter(
    prefix="/comments",
    tags=["comments"],
)


# ------------------------------------------------------------------ #
# POST /posts/{post_id}/comments — create comment or reply
# ------------------------------------------------------------------ #


@post_comments_router.post(
    "",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_age_verified)],
    summary="Create a comment or reply on a post",
)
async def create_new_comment(
    post_id: uuid.UUID,
    payload: CreateCommentRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
    push_adapter: PushAdapter = Depends(get_push_adapter),
) -> CommentResponse:
    """
    Create a top-level comment (parent_id omitted) or a reply (parent_id set).

    Notification triggers (all fire-and-forget via BackgroundTasks):
      - New top-level comment → notifies post author (unless self-commenting)
      - Reply                 → notifies parent comment author (unless self-replying)
      - @mention in content  → notifies each mentioned user (unless self-mention)
    """
    comment = await create_comment(payload, post_id, current_user, db)

    # ------------------------------------------------------------------ #
    # Notification 1: post author — new top-level comment
    # ------------------------------------------------------------------ #
    if payload.parent_id is None:
        post_row = (
            await db.execute(select(Post.author_id).where(Post.post_id == post_id))
        ).first()
        post_author_id = post_row.author_id if post_row else None

        if post_author_id and post_author_id != current_user.user_id:
            post_author_tokens = await get_tokens_for_user(
                user_id=post_author_id, db=db
            )
            if post_author_tokens:
                background_tasks.add_task(
                    dispatch_push,
                    adapter=push_adapter,
                    device_tokens=post_author_tokens,
                    title="New comment",
                    body=f"@{current_user.username} commented on your post",
                    data={
                        "type": "comment",
                        "post_id": str(post_id),
                        "comment_id": str(comment.comment_id),
                    },
                )

    # ------------------------------------------------------------------ #
    # Notification 2: parent comment author — new reply
    # ------------------------------------------------------------------ #
    if payload.parent_id is not None:
        parent_tokens, parent_author_id = await get_tokens_for_comment_author(
            comment_id=payload.parent_id, db=db
        )
        if parent_tokens and parent_author_id != current_user.user_id:
            background_tasks.add_task(
                dispatch_push,
                adapter=push_adapter,
                device_tokens=parent_tokens,
                title="New reply",
                body=f"@{current_user.username} replied to your comment",
                data={
                    "type": "reply",
                    "post_id": str(post_id),
                    "comment_id": str(comment.comment_id),
                },
            )

    # ------------------------------------------------------------------ #
    # Notification 3: @mentioned users
    # ------------------------------------------------------------------ #
    mentions = extract_mentions(comment.content_text)
    if mentions:
        username_to_tokens = await get_tokens_for_usernames(mentions, db=db)
        for mentioned_username, tokens in username_to_tokens.items():
            if tokens and mentioned_username != current_user.username.lower():
                background_tasks.add_task(
                    dispatch_push,
                    adapter=push_adapter,
                    device_tokens=tokens,
                    title="You were mentioned",
                    body=f"@{current_user.username} mentioned you in a comment",
                    data={
                        "type": "mention",
                        "post_id": str(post_id),
                        "comment_id": str(comment.comment_id),
                    },
                )

    return CommentResponse(
        comment_id=comment.comment_id,
        post_id=comment.post_id,
        author_id=comment.author_id,
        author_username=current_user.username,
        parent_id=comment.parent_id,
        content_text=comment.content_text,
        reply_count=0,
        created_at=comment.created_at,
    )


# ------------------------------------------------------------------ #
# GET /posts/{post_id}/comments — list top-level comments (public)
# ------------------------------------------------------------------ #


@post_comments_router.get(
    "",
    response_model=list[CommentResponse],
    summary="List top-level comments on a post",
)
async def get_post_comments(
    post_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
) -> list[CommentResponse]:
    """Returns top-level comments (parent_id IS NULL) oldest-first with reply counts."""
    rows = await list_post_comments(post_id=post_id, skip=skip, limit=limit, db=db)
    return [CommentResponse(**row) for row in rows]


# ------------------------------------------------------------------ #
# GET /comments/{comment_id}/replies — list replies (public)
# ------------------------------------------------------------------ #


@comments_router.get(
    "/{comment_id}/replies",
    response_model=list[CommentResponse],
    summary="List replies to a comment",
)
async def get_comment_replies(
    comment_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
) -> list[CommentResponse]:
    """Returns replies to a specific comment, oldest-first."""
    rows = await list_comment_replies(
        comment_id=comment_id, skip=skip, limit=limit, db=db
    )
    return [CommentResponse(**row) for row in rows]


# ------------------------------------------------------------------ #
# DELETE /comments/{comment_id} — delete own comment (auth required)
# ------------------------------------------------------------------ #


@comments_router.delete(
    "/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a comment",
)
async def delete_own_comment(
    comment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> None:
    """Delete your own comment. Also removes all replies via cascade."""
    await delete_comment(
        comment_id=comment_id, current_user=current_user, db=db
    )
