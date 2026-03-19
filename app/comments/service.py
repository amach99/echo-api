"""
app/comments/service.py — Comment business logic.

create_comment:
    Validates post exists + parent_id (if given) belongs to the same post.
    Raises 404 on missing resources.

list_post_comments:
    Returns top-level comments (parent_id IS NULL) with reply_count.
    Single JOIN + subquery — no N+1 queries.

list_comment_replies:
    Returns direct replies to a specific comment_id, oldest-first.

delete_comment:
    Author-only deletion. Raises 403 if a different user attempts deletion.
    DB CASCADE removes all replies when a top-level comment is deleted.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.comments.schemas import CommentResponse, CreateCommentRequest
from app.models.comment import Comment
from app.models.post import Post
from app.models.user import User


async def create_comment(
    payload: CreateCommentRequest,
    post_id: uuid.UUID,
    author: User,
    db: AsyncSession,
) -> Comment:
    """Create a top-level comment or a reply on a post."""

    # 1. Verify post exists
    post_result = await db.execute(select(Post).where(Post.post_id == post_id))
    if post_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "POST_NOT_FOUND", "message": "Post not found."},
        )

    # 2. If replying, validate parent belongs to the same post
    if payload.parent_id is not None:
        parent_result = await db.execute(
            select(Comment).where(
                Comment.comment_id == payload.parent_id,
                Comment.post_id == post_id,
            )
        )
        if parent_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "PARENT_COMMENT_NOT_FOUND",
                    "message": "Parent comment not found on this post.",
                },
            )

    comment = Comment(
        post_id=post_id,
        author_id=author.user_id,
        parent_id=payload.parent_id,
        content_text=payload.content_text,
    )
    db.add(comment)
    await db.flush()
    return comment


async def list_post_comments(
    post_id: uuid.UUID,
    skip: int,
    limit: int,
    db: AsyncSession,
) -> list[dict]:
    """
    Return top-level comments (parent_id IS NULL) for a post, oldest-first.
    Includes reply_count per comment. Single query using a subquery — no N+1.
    """
    # Subquery: count direct replies per top-level comment
    reply_count_subq = (
        select(
            Comment.parent_id,
            func.count(Comment.comment_id).label("reply_count"),
        )
        .where(Comment.parent_id.is_not(None))
        .group_by(Comment.parent_id)
        .subquery()
    )

    stmt = (
        select(
            Comment,
            User.username,
            func.coalesce(reply_count_subq.c.reply_count, 0).label("reply_count"),
        )
        .join(User, Comment.author_id == User.user_id)
        .outerjoin(
            reply_count_subq,
            Comment.comment_id == reply_count_subq.c.parent_id,
        )
        .where(Comment.post_id == post_id, Comment.parent_id.is_(None))
        .order_by(Comment.created_at.asc())
        .offset(skip)
        .limit(limit)
    )

    rows = (await db.execute(stmt)).all()

    return [
        {
            "comment_id": row.Comment.comment_id,
            "post_id": row.Comment.post_id,
            "author_id": row.Comment.author_id,
            "author_username": row.username,
            "parent_id": row.Comment.parent_id,
            "content_text": row.Comment.content_text,
            "reply_count": row.reply_count,
            "created_at": row.Comment.created_at,
        }
        for row in rows
    ]


async def list_comment_replies(
    comment_id: uuid.UUID,
    skip: int,
    limit: int,
    db: AsyncSession,
) -> list[dict]:
    """
    Return direct replies to a comment, oldest-first.
    Raises 404 if the parent comment does not exist.
    """
    parent_result = await db.execute(
        select(Comment).where(Comment.comment_id == comment_id)
    )
    if parent_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "COMMENT_NOT_FOUND", "message": "Comment not found."},
        )

    stmt = (
        select(Comment, User.username)
        .join(User, Comment.author_id == User.user_id)
        .where(Comment.parent_id == comment_id)
        .order_by(Comment.created_at.asc())
        .offset(skip)
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()

    return [
        {
            "comment_id": row.Comment.comment_id,
            "post_id": row.Comment.post_id,
            "author_id": row.Comment.author_id,
            "author_username": row.username,
            "parent_id": row.Comment.parent_id,
            "content_text": row.Comment.content_text,
            "reply_count": 0,
            "created_at": row.Comment.created_at,
        }
        for row in rows
    ]


async def delete_comment(
    comment_id: uuid.UUID,
    current_user: User,
    db: AsyncSession,
) -> None:
    """
    Delete a comment. Only the author may delete their own comment.
    DB CASCADE removes all replies automatically.
    """
    result = await db.execute(
        select(Comment).where(Comment.comment_id == comment_id)
    )
    comment = result.scalar_one_or_none()

    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "COMMENT_NOT_FOUND", "message": "Comment not found."},
        )

    if comment.author_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN",
                "message": "You can only delete your own comments.",
            },
        )

    await db.delete(comment)
