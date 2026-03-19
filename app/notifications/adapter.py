"""
app/notifications/adapter.py — Push notification delivery adapters.

Follows the same swappable pattern as app/email/adapter.py and
app/verification/adapter.py.

Providers:
  mock — Logs to stdout. Used in all tests and local dev. No external calls.
  apns — Apple Push Notification service (iOS). Requires Apple Developer account.
  fcm  — Firebase Cloud Messaging (Android). Requires Firebase project.

Swap with a single .env change:
  PUSH_PROVIDER=mock   (default — no credentials needed)
  PUSH_PROVIDER=apns   (requires APNS_KEY_ID, APNS_TEAM_ID, APNS_BUNDLE_ID, APNS_PRIVATE_KEY)
  PUSH_PROVIDER=fcm    (requires FCM_SERVER_KEY)

All adapters swallow delivery errors and log them — a failed push never
crashes the request that triggered it.
"""

import json
import time
import uuid
from typing import Protocol

import httpx

from app.config import get_settings

settings = get_settings()


# ------------------------------------------------------------------ #
# Protocol (interface contract)
# ------------------------------------------------------------------ #


class PushAdapter(Protocol):
    """Protocol all push adapters must satisfy."""

    async def send(
        self,
        token: str,
        platform: str,
        title: str,
        body: str,
        data: dict | None = None,
    ) -> None:
        """Send a push notification to a single device token."""
        ...


# ------------------------------------------------------------------ #
# Mock adapter (tests + local dev)
# ------------------------------------------------------------------ #


class MockPushAdapter:
    """
    Logs push details to stdout. Zero external calls.
    Active when PUSH_PROVIDER=mock (the default).
    """

    async def send(
        self,
        token: str,
        platform: str,
        title: str,
        body: str,
        data: dict | None = None,
    ) -> None:
        print(
            f"[MockPush] → platform={platform} "
            f"title={title!r} body={body!r} "
            f"token={token[:16]}... data={data}"
        )


# ------------------------------------------------------------------ #
# APNs adapter (iOS production)
# ------------------------------------------------------------------ #


class APNsAdapter:
    """
    Apple Push Notification service — HTTP/2 API with JWT auth.
    https://developer.apple.com/documentation/usernotifications

    Required .env settings:
      PUSH_PROVIDER=apns
      APNS_KEY_ID=<10-char key ID from Apple Developer portal>
      APNS_TEAM_ID=<10-char Team ID from Apple Developer portal>
      APNS_BUNDLE_ID=com.echosocial.app
      APNS_PRIVATE_KEY=<contents of AuthKey_XXXXXXXXXX.p8 file>

    APNs uses JWT tokens signed with ES256 (your p8 private key).
    Tokens are valid for 1 hour; we generate a fresh one per request
    (production code would cache and rotate these).
    """

    _APNS_HOST_PROD = "https://api.push.apple.com"
    _APNS_HOST_SANDBOX = "https://api.sandbox.push.apple.com"

    def _make_jwt(self) -> str:
        """Build an APNs provider JWT. Requires PyJWT with cryptography extra."""
        try:
            import jwt as pyjwt  # PyJWT

            token = pyjwt.encode(
                payload={
                    "iss": settings.APNS_TEAM_ID,
                    "iat": int(time.time()),
                },
                key=settings.APNS_PRIVATE_KEY,
                algorithm="ES256",
                headers={"kid": settings.APNS_KEY_ID},
            )
            return token
        except Exception as exc:
            print(f"[APNs] JWT generation failed: {exc}")
            return ""

    async def send(
        self,
        token: str,
        platform: str,
        title: str,
        body: str,
        data: dict | None = None,
    ) -> None:
        if platform != "apns":
            return

        host = (
            self._APNS_HOST_SANDBOX
            if settings.ENV != "production"
            else self._APNS_HOST_PROD
        )
        url = f"{host}/3/device/{token}"

        payload: dict = {
            "aps": {
                "alert": {"title": title, "body": body},
                "sound": "default",
                "badge": 1,
            }
        }
        if data:
            payload.update(data)

        headers = {
            "authorization": f"bearer {self._make_jwt()}",
            "apns-topic": settings.APNS_BUNDLE_ID,
            "apns-push-type": "alert",
            "apns-priority": "10",
            "apns-id": str(uuid.uuid4()),
        }

        try:
            async with httpx.AsyncClient(http2=True, timeout=10.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code not in (200,):
                    print(f"[APNs] Delivery failed ({resp.status_code}): {resp.text}")
        except Exception as exc:  # noqa: BLE001
            print(f"[APNs] Delivery error for token {token[:16]}...: {exc}")


# ------------------------------------------------------------------ #
# FCM adapter (Android production)
# ------------------------------------------------------------------ #


class FCMAdapter:
    """
    Firebase Cloud Messaging — Legacy HTTP API.
    https://firebase.google.com/docs/cloud-messaging/http-server-ref

    Required .env settings:
      PUSH_PROVIDER=fcm
      FCM_SERVER_KEY=<Server Key from Firebase Console → Project Settings → Cloud Messaging>

    Note: Google deprecated the legacy API in favour of FCM v1 (OAuth2-based).
    Upgrade to v1 when you set up the Firebase service account. For now the
    legacy key is simpler and still functional.
    """

    _FCM_URL = "https://fcm.googleapis.com/fcm/send"

    async def send(
        self,
        token: str,
        platform: str,
        title: str,
        body: str,
        data: dict | None = None,
    ) -> None:
        if platform != "fcm":
            return

        payload = {
            "to": token,
            "notification": {"title": title, "body": body, "sound": "default"},
            "data": data or {},
            "priority": "high",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    self._FCM_URL,
                    json=payload,
                    headers={
                        "Authorization": f"key={settings.FCM_SERVER_KEY}",
                        "Content-Type": "application/json",
                    },
                )
                result = resp.json()
                if result.get("failure", 0) > 0:
                    print(f"[FCM] Delivery failed: {json.dumps(result)}")
        except Exception as exc:  # noqa: BLE001
            print(f"[FCM] Delivery error for token {token[:16]}...: {exc}")


# ------------------------------------------------------------------ #
# Dependency factory
# ------------------------------------------------------------------ #


def get_push_adapter() -> PushAdapter:
    """
    FastAPI dependency — returns the adapter configured by PUSH_PROVIDER.

    mock → MockPushAdapter (default; no external calls)
    apns → APNsAdapter (iOS production)
    fcm  → FCMAdapter (Android production)
    """
    match settings.PUSH_PROVIDER:
        case "apns":
            return APNsAdapter()
        case "fcm":
            return FCMAdapter()
        case _:
            return MockPushAdapter()  # "mock" + any unknown value
