"""app/verification/schemas.py — Pydantic schemas for verification endpoints."""

from pydantic import BaseModel


class InitiateVerificationResponse(BaseModel):
    """Returned by POST /verification/initiate."""

    session_url: str
    message: str = "Verification session created. Redirect the user to session_url."


class VerificationCallbackPayload(BaseModel):
    """
    Expected body from Yoti webhook (SESSION_COMPLETION notification).

    session_id        — Yoti session identifier
    user_tracking_id  — our user_id, passed when the session was created
    topic             — notification type (always "SESSION_COMPLETION" here)
    """

    session_id: str
    user_tracking_id: str
    topic: str = "SESSION_COMPLETION"
