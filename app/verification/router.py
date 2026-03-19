"""
app/verification/router.py — Age verification endpoints.

POST /verification/initiate
    Requires auth. Creates a Yoti session and returns the redirect URL.
    Client must redirect the user to session_url to complete the flow.

POST /verification/callback
    No auth — called by Yoti's webhook system.
    Validates HMAC-SHA256 signature, fetches result, sets is_verified_human=True.
"""

import json
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_async_db
from app.models.user import User
from app.verification.adapter import AgeVerificationAdapter, get_verification_adapter
from app.verification.schemas import InitiateVerificationResponse
from app.verification.service import handle_verification_callback, initiate_age_verification

router = APIRouter(prefix="/verification", tags=["verification"])


@router.post(
    "/initiate",
    response_model=InitiateVerificationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start an age verification session",
)
async def initiate_verification(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
    adapter: AgeVerificationAdapter = Depends(get_verification_adapter),
) -> InitiateVerificationResponse:
    """
    Creates a Yoti Age Estimation session for the authenticated user.
    Redirect the user to the returned `session_url` to complete verification.
    After the user finishes, Yoti calls POST /verification/callback automatically.
    """
    callback_url = str(request.url_for("verification_callback"))
    result = await initiate_age_verification(current_user, db, adapter, callback_url)
    return InitiateVerificationResponse(session_url=result.session_url)


@router.post(
    "/callback",
    status_code=status.HTTP_200_OK,
    summary="Yoti webhook — verification result",
    name="verification_callback",
)
async def verification_callback(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    adapter: AgeVerificationAdapter = Depends(get_verification_adapter),
    x_yoti_auth_token: str | None = Header(default=None),
) -> dict[str, str]:
    """
    Called by Yoti when a SESSION_COMPLETION event occurs.

    Security:
      - HMAC-SHA256 webhook signature validated via X-Yoti-Auth-Token header.
      - user_tracking_id in the payload maps to our internal user_id.
      - is_verified_human is only set server-side here — never from client input.
    """
    raw_body = await request.body()

    try:
        payload: dict = json.loads(raw_body)
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_PAYLOAD", "message": "Cannot parse webhook body as JSON."},
        ) from exc

    session_id: str | None = payload.get("session_id")
    user_tracking_id: str | None = payload.get("user_tracking_id")

    if not session_id or not user_tracking_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "MISSING_FIELDS",
                "message": "Both session_id and user_tracking_id are required.",
            },
        )

    try:
        user_id = uuid.UUID(user_tracking_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_USER_ID",
                "message": "user_tracking_id must be a valid UUID.",
            },
        ) from exc

    verified = await handle_verification_callback(
        session_id=session_id,
        user_id=user_id,
        raw_body=raw_body,
        signature_header=x_yoti_auth_token or "",
        db=db,
        adapter=adapter,
    )

    return {"status": "processed", "age_verified": str(verified).lower()}
