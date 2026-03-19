"""
app/verification/service.py — Verification business logic.

initiate_age_verification:
    Delegates to the adapter to create a session; returns the redirect URL.

handle_verification_callback:
    Validates the Yoti webhook, checks the result, and sets
    User.is_verified_human = True when age is confirmed.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.verification.adapter import AgeVerificationAdapter, SessionCreatedResult


async def initiate_age_verification(
    user: User,
    db: AsyncSession,
    adapter: AgeVerificationAdapter,
    callback_url: str,
) -> SessionCreatedResult:
    """
    Start an age-verification session for the given user.
    Returns the session_id and the URL to redirect the user to.
    db is accepted for future use (e.g. storing session_id → user_id mapping).
    """
    return await adapter.initiate_session(user.user_id, callback_url)


async def handle_verification_callback(
    session_id: str,
    user_id: uuid.UUID,
    raw_body: bytes,
    signature_header: str,
    db: AsyncSession,
    adapter: AgeVerificationAdapter,
) -> bool:
    """
    Process a Yoti webhook notification.

    1. Validates the signature (adapter raises HTTP 403 on mismatch).
    2. Fetches the final verification outcome.
    3. Sets User.is_verified_human = True if age is confirmed.

    Returns True when the user was verified, False otherwise.
    """
    result = await adapter.get_session_result(session_id, raw_body, signature_header)

    if result.age_verified:
        stmt = select(User).where(User.user_id == user_id)
        row = await db.execute(stmt)
        user = row.scalar_one_or_none()
        if user is not None:
            user.is_verified_human = True
            await db.flush()

    return result.age_verified
