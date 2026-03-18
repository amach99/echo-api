"""
tests/factories.py — Test data factory helpers.
All factory functions are async and accept an AsyncSession.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import hash_password
from app.models.echo import Echo
from app.models.follow import Follow
from app.models.like import Like
from app.models.mute_echo import MuteEcho
from app.models.post import Post
from app.models.user import AccountType, User
from app.models.vote import Vote


async def create_user(
    db: AsyncSession,
    *,
    username: str | None = None,
    email: str | None = None,
    account_type: AccountType = AccountType.HUMAN,
    is_verified_human: bool = True,
    password: str = "testpassword123",
    linked_human_id: uuid.UUID | None = None,
) -> User:
    uid = uuid.uuid4()
    user = User(
        user_id=uid,
        username=username or f"user_{uid.hex[:8]}",
        email=email or f"{uid.hex[:8]}@test.com",
        account_type=account_type,
        is_verified_human=is_verified_human,
        password_hash=hash_password(password),
        linked_human_id=linked_human_id,
    )
    db.add(user)
    await db.flush()
    return user


async def create_human(db: AsyncSession, **kwargs) -> User:
    return await create_user(db, account_type=AccountType.HUMAN,
                              is_verified_human=True, **kwargs)


async def create_business(db: AsyncSession, linked_human: User, **kwargs) -> User:
    return await create_user(db, account_type=AccountType.BUSINESS,
                              is_verified_human=True,
                              linked_human_id=linked_human.user_id, **kwargs)


async def create_unverified_user(db: AsyncSession, **kwargs) -> User:
    return await create_user(db, is_verified_human=False, **kwargs)


async def create_post(
    db: AsyncSession,
    author: User,
    *,
    content_text: str = "Test post content",
    media_url: str | None = None,
) -> Post:
    post = Post(
        author_id=author.user_id,
        content_text=content_text,
        media_url=media_url,
        is_pulse_post=author.is_pulse_account,
    )
    db.add(post)
    await db.flush()
    return post


async def create_life_post(db: AsyncSession, author: User, **kwargs) -> Post:
    """Create a Life Feed post (Human author)."""
    assert not author.is_pulse_account, "Life posts must be from Human accounts"
    return await create_post(db, author, **kwargs)


async def create_pulse_post(db: AsyncSession, author: User, **kwargs) -> Post:
    """Create a Pulse Feed post (Business/Meme/Info author)."""
    assert author.is_pulse_account, "Pulse posts must be from non-Human accounts"
    return await create_post(db, author, **kwargs)


async def create_follow(db: AsyncSession, follower: User, following: User) -> Follow:
    follow = Follow(follower_id=follower.user_id, following_id=following.user_id)
    db.add(follow)
    await db.flush()
    return follow


async def create_echo(db: AsyncSession, echoer: User, post: Post) -> Echo:
    echo = Echo(echoer_id=echoer.user_id, post_id=post.post_id)
    db.add(echo)
    await db.flush()
    return echo


async def create_mute(db: AsyncSession, user: User, muted_user: User) -> MuteEcho:
    mute = MuteEcho(user_id=user.user_id, muted_user_id=muted_user.user_id)
    db.add(mute)
    await db.flush()
    return mute


async def create_like(db: AsyncSession, user: User, post: Post) -> Like:
    like = Like(user_id=user.user_id, post_id=post.post_id)
    db.add(like)
    await db.flush()
    return like


async def create_vote(
    db: AsyncSession, user: User, post: Post, vote_value: int = 1
) -> Vote:
    vote = Vote(user_id=user.user_id, post_id=post.post_id, vote_value=vote_value)
    db.add(vote)
    await db.flush()
    return vote
