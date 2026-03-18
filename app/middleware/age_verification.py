"""
app/middleware/age_verification.py — Texas SB 2420 / Digital Authenticity Act.

require_age_verified is a FastAPI Depends that MUST be applied as a
router-level dependency on ALL write-action routers.

Usage (in every write-action router):
    router = APIRouter(dependencies=[Depends(require_age_verified)])

If a user's is_verified_human flag is False, all write actions return:
    HTTP 403 FORBIDDEN  {"code": "AGE_VERIFICATION_REQUIRED"}

This is the single most critical middleware in the application.
A missing dependency on a write router is a CRITICAL bug.
"""

from fastapi import Depends, HTTPException, status

from app.auth.dependencies import get_current_user
from app.models.user import User

_AGE_VERIFICATION_EXCEPTION = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail={
        "code": "AGE_VERIFICATION_REQUIRED",
        "message": (
            "You must complete 18+ ID verification before performing this action. "
            "Please visit /verification/initiate to begin the verification process."
        ),
    },
)


async def require_age_verified(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency — verifies the authenticated user has passed Level 3 ID verification.

    Apply at router level:
        router = APIRouter(dependencies=[Depends(require_age_verified)])

    Returns the verified User so individual endpoints can use it:
        async def create_post(user: User = Depends(require_age_verified)):
            ...
    """
    if not current_user.is_verified_human:
        raise _AGE_VERIFICATION_EXCEPTION
    return current_user
