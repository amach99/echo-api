"""
app/auth/dependencies.py — FastAPI dependency for extracting the current user.

get_current_user:
  - Extracts Bearer token from Authorization header
  - Decodes and validates the JWT
  - Loads the User from the database
  - Raises 401 if token is missing, expired, or user not found
"""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import decode_access_token, get_user_by_id
from app.database import get_async_db
from app.models.user import User

_bearer_scheme = HTTPBearer(auto_error=True)

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail={"code": "INVALID_TOKEN", "message": "Could not validate credentials."},
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_async_db),
) -> User:
    """
    Validate the Bearer token and return the authenticated User.
    Raises HTTP 401 on any failure — expired, tampered, or user deleted.
    """
    try:
        payload = decode_access_token(credentials.credentials)
        if payload.get("type") != "access":
            raise _CREDENTIALS_EXCEPTION
        user_id_str: str | None = payload.get("sub")
        if not user_id_str:
            raise _CREDENTIALS_EXCEPTION
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise _CREDENTIALS_EXCEPTION

    user = await get_user_by_id(user_id, db)
    if user is None:
        raise _CREDENTIALS_EXCEPTION

    return user
