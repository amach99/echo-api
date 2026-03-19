"""
app/verification/adapter.py — Age verification adapter abstraction.

Supports multiple providers via the AgeVerificationAdapter protocol.
The active provider is selected at startup from ID_VERIFY_PROVIDER in config.

Providers:
  mock  — Auto-approves every session; used in tests and development.
  yoti  — Yoti Age Estimation API (production).

Usage:
  Inject via FastAPI dependency:
    adapter: AgeVerificationAdapter = Depends(get_verification_adapter)
"""

import hashlib
import hmac
import uuid
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.config import get_settings

settings = get_settings()


# ------------------------------------------------------------------ #
# Result types
# ------------------------------------------------------------------ #


@dataclass(frozen=True)
class SessionCreatedResult:
    """Returned by adapter.initiate_session() — the URL to redirect the user to."""

    session_id: str
    session_url: str


@dataclass(frozen=True)
class VerificationResult:
    """Returned by adapter.get_session_result() — the final outcome."""

    session_id: str
    age_verified: bool
    confidence: float  # 0.0–1.0


# ------------------------------------------------------------------ #
# Protocol (structural interface)
# ------------------------------------------------------------------ #


class AgeVerificationAdapter(Protocol):
    """Protocol that all verification adapter implementations must satisfy."""

    async def initiate_session(
        self, user_id: uuid.UUID, callback_url: str
    ) -> SessionCreatedResult:
        """
        Start a verification session for user_id.
        callback_url: our /verification/callback endpoint URL.
        Returns the URL to send the user to.
        """
        ...

    async def get_session_result(
        self,
        session_id: str,
        raw_body: bytes,
        signature_header: str,
    ) -> VerificationResult:
        """
        Validate the webhook signature and return the outcome.
        Raises HTTPException 403 if signature is invalid.
        """
        ...


# ------------------------------------------------------------------ #
# Mock adapter (development + tests)
# ------------------------------------------------------------------ #


class MockVerificationAdapter:
    """
    Development and test adapter.

    initiate_session  → returns a deterministic fake URL.
    get_session_result → always approves; any signature accepted.
    """

    async def initiate_session(
        self, user_id: uuid.UUID, callback_url: str
    ) -> SessionCreatedResult:
        fake_session_id = str(uuid.uuid4())
        return SessionCreatedResult(
            session_id=fake_session_id,
            session_url=f"https://mock.yoti.test/verify/{fake_session_id}",
        )

    async def get_session_result(
        self,
        session_id: str,
        raw_body: bytes,
        signature_header: str,
    ) -> VerificationResult:
        # Mock always approves — no signature check
        return VerificationResult(
            session_id=session_id,
            age_verified=True,
            confidence=1.0,
        )


# ------------------------------------------------------------------ #
# Yoti adapter (production)
# ------------------------------------------------------------------ #


class YotiAgeEstimationAdapter:
    """
    Production adapter for the Yoti Age Estimation REST API.

    Authentication uses the Yoti SDK ID + RSA private key (ID_VERIFY_API_KEY).
    Webhook integrity is validated with HMAC-SHA256 using ID_VERIFY_WEBHOOK_SECRET.

    Yoti API docs: https://developers.yoti.com/age-estimation/
    """

    _BASE_URL = "https://api.yoti.com/age-verification/v1"

    def __init__(self) -> None:
        self._client_id = settings.ID_VERIFY_CLIENT_ID
        self._api_key = settings.ID_VERIFY_API_KEY
        self._webhook_secret = settings.ID_VERIFY_WEBHOOK_SECRET

    async def initiate_session(
        self, user_id: uuid.UUID, callback_url: str
    ) -> SessionCreatedResult:
        """Create a Yoti Age Estimation session and return the redirect URL."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self._BASE_URL}/sessions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "X-Yoti-SDK-Id": self._client_id,
                },
                json={
                    "client_session_token_ttl": 900,   # 15 minutes
                    "resources_ttl": 86400,            # 24 hours
                    "user_tracking_id": str(user_id),
                    "notifications": {
                        "endpoint": callback_url,
                        "topics": ["SESSION_COMPLETION"],
                    },
                    "requested_checks": [
                        {"type": "ID_DOCUMENT_AUTHENTICITY"},
                        {"type": "LIVENESS"},
                    ],
                    "required_documents": [{"type": "ID_DOCUMENT"}],
                },
            )
            resp.raise_for_status()
            data = resp.json()

        return SessionCreatedResult(
            session_id=data["session_id"],
            session_url=data["client_session_token_url"],
        )

    async def get_session_result(
        self,
        session_id: str,
        raw_body: bytes,
        signature_header: str,
    ) -> VerificationResult:
        """
        Validate HMAC-SHA256 webhook signature then fetch the session outcome.
        Raises HTTP 403 if the signature does not match.
        """
        from fastapi import HTTPException, status

        # Constant-time HMAC comparison to prevent timing attacks
        expected = hmac.new(
            self._webhook_secret.encode(),
            raw_body,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, signature_header or ""):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "INVALID_WEBHOOK_SIGNATURE",
                    "message": "Webhook signature mismatch.",
                },
            )

        # Fetch final session outcome from Yoti
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{self._BASE_URL}/sessions/{session_id}",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "X-Yoti-SDK-Id": self._client_id,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        state = data.get("state", "")
        checks = data.get("checks", [])

        age_verified = state == "COMPLETED" and any(
            c.get("type") == "ID_DOCUMENT_AUTHENTICITY" and c.get("state") == "DONE"
            for c in checks
        )

        return VerificationResult(
            session_id=session_id,
            age_verified=age_verified,
            confidence=1.0 if age_verified else 0.0,
        )


# ------------------------------------------------------------------ #
# Dependency factory
# ------------------------------------------------------------------ #


def get_verification_adapter() -> AgeVerificationAdapter:
    """
    FastAPI dependency — returns the adapter configured by ID_VERIFY_PROVIDER.

    mock  → MockVerificationAdapter (no external calls, always approves)
    yoti  → YotiAgeEstimationAdapter (production Yoti REST API)
    """
    provider = settings.ID_VERIFY_PROVIDER
    if provider == "mock":
        return MockVerificationAdapter()
    if provider == "yoti":
        return YotiAgeEstimationAdapter()
    raise ValueError(f"Unknown ID_VERIFY_PROVIDER: {provider!r}")
