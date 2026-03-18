"""
app/auth/service.py — Authentication business logic.

JWT strategy:
  - Access tokens:  short-lived (15 min), contain user_id + is_verified_human + account_type
  - Refresh tokens: long-lived (7 days), contain only user_id + token_family_id
  - Refresh rotation: each refresh issues a new pair; old refresh token is invalidated
  - Token family stored in `refresh_tokens` table for theft detection
"""

import uuid
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import RegisterRequest
from app.config import get_settings
from app.models.user import AccountType, User

settings = get_settings()

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ------------------------------------------------------------------ #
# Password helpers
# ------------------------------------------------------------------ #

def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# ------------------------------------------------------------------ #
# JWT helpers
# ------------------------------------------------------------------ #

def create_access_token(
    user_id: uuid.UUID,
    is_verified_human: bool,
    account_type: str,
) -> str:
    """Short-lived access token (15 min). Contains identity claims."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "is_verified_human": is_verified_human,
        "account_type": account_type,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")


def create_refresh_token(user_id: uuid.UUID, family_id: uuid.UUID) -> str:
    """Long-lived refresh token (7 days). Contains minimal claims."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "family_id": str(family_id),
        "iat": now,
        "exp": now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.JWT_REFRESH_SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    """Decode and validate an access token. Raises JWTError on failure."""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])


def decode_refresh_token(token: str) -> dict:
    """Decode and validate a refresh token. Raises JWTError on failure."""
    return jwt.decode(token, settings.JWT_REFRESH_SECRET_KEY, algorithms=["HS256"])


# ------------------------------------------------------------------ #
# User operations
# ------------------------------------------------------------------ #

async def register_user(payload: RegisterRequest, db: AsyncSession) -> User:
    """Create a new user. Validates uniqueness and linked_human requirement."""
    # Check username uniqueness
    result = await db.execute(select(User).where(User.username == payload.username))
    if result.scalar_one_or_none():
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "USERNAME_TAKEN", "message": "Username is already in use."},
        )

    # Check email uniqueness
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none():
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "EMAIL_TAKEN", "message": "Email is already registered."},
        )

    # Validate linked_human_id exists and is a Human account
    if payload.linked_human_id is not None:
        result = await db.execute(
            select(User).where(
                User.user_id == payload.linked_human_id,
                User.account_type == AccountType.HUMAN,
                User.is_verified_human.is_(True),
            )
        )
        if not result.scalar_one_or_none():
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "INVALID_LINKED_HUMAN",
                    "message": "linked_human_id must reference a verified Human account.",
                },
            )

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        account_type=AccountType(payload.account_type),
        linked_human_id=payload.linked_human_id,
        is_verified_human=False,  # always starts unverified
    )
    db.add(user)
    await db.flush()  # get user_id before commit
    return user


async def authenticate_user(
    email: str, password: str, db: AsyncSession
) -> User:
    """Verify credentials. Raises HTTPException on failure."""
    from fastapi import HTTPException, status

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "Email or password is incorrect."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_user_by_id(user_id: uuid.UUID, db: AsyncSession) -> User | None:
    result = await db.execute(select(User).where(User.user_id == user_id))
    return result.scalar_one_or_none()
