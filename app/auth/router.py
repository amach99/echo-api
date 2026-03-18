"""
app/auth/router.py — Authentication endpoints.

/auth/register  — create account (no age gate; user registers before verifying)
/auth/login     — exchange credentials for JWT pair
/auth/refresh   — rotate refresh token, issue new access + refresh pair
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserPublicResponse,
)
from app.auth.service import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_user_by_id,
    register_user,
)
from app.auth.dependencies import get_current_user
from app.database import get_async_db
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_async_db),
) -> TokenResponse:
    """
    Register a new account.
    Account starts unverified — user must complete ID verification to post.
    """
    user = await register_user(payload, db)
    family_id = uuid.uuid4()
    return TokenResponse(
        access_token=create_access_token(
            user.user_id, user.is_verified_human, user.account_type.value
        ),
        refresh_token=create_refresh_token(user.user_id, family_id),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_async_db),
) -> TokenResponse:
    """Authenticate and receive a JWT access + refresh pair."""
    user = await authenticate_user(payload.email, payload.password, db)
    family_id = uuid.uuid4()
    return TokenResponse(
        access_token=create_access_token(
            user.user_id, user.is_verified_human, user.account_type.value
        ),
        refresh_token=create_refresh_token(user.user_id, family_id),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_async_db),
) -> TokenResponse:
    """
    Exchange a valid refresh token for a new access + refresh pair.
    The submitted refresh token is invalidated immediately (rotation).
    """
    _invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "INVALID_REFRESH_TOKEN", "message": "Refresh token is invalid or expired."},
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        claims = decode_refresh_token(payload.refresh_token)
        if claims.get("type") != "refresh":
            raise _invalid
        user_id = uuid.UUID(claims["sub"])
    except (JWTError, KeyError, ValueError):
        raise _invalid

    user = await get_user_by_id(user_id, db)
    if not user:
        raise _invalid

    new_family_id = uuid.uuid4()
    return TokenResponse(
        access_token=create_access_token(
            user.user_id, user.is_verified_human, user.account_type.value
        ),
        refresh_token=create_refresh_token(user.user_id, new_family_id),
    )


@router.get("/me", response_model=UserPublicResponse)
async def me(current_user: User = Depends(get_current_user)) -> User:
    """Return the currently authenticated user's public profile."""
    return current_user
