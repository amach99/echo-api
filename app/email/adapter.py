"""
app/email/adapter.py — Email delivery adapter abstraction.

Follows the same swappable adapter pattern as app/verification/adapter.py.

Providers:
  mock   — Logs to stdout. Used in all tests and local dev. No external calls.
  resend — Resend REST API (resend.com). Free tier: 3,000 emails/month.

Usage:
  Inject via FastAPI dependency:
    adapter: EmailAdapter = Depends(get_email_adapter)

  Or dispatch as a background task so email never blocks the HTTP response:
    background_tasks.add_task(adapter.send_invite, to=..., inviter_username=..., token=...)
"""

from typing import Protocol

import httpx

from app.config import get_settings

settings = get_settings()

# ------------------------------------------------------------------ #
# Invite email template
# ------------------------------------------------------------------ #

_INVITE_SUBJECT = "{inviter_username} invited you to Echo Social"

_INVITE_HTML = """\
<!DOCTYPE html>
<html>
<body style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 24px;">
  <h2>You've been invited to Echo Social</h2>
  <p>
    <strong>@{inviter_username}</strong> has saved you a spot on
    <strong>Echo Social</strong> — a verified, 18+ platform built for real humans,
    not bots or brands.
  </p>
  <p>
    <a href="https://echosocial.app/join?token={token}"
       style="background:#000;color:#fff;padding:12px 24px;border-radius:6px;
              text-decoration:none;display:inline-block;margin:16px 0;">
      Accept your invite
    </a>
  </p>
  <p style="color:#666;font-size:13px;">
    This invite expires in 7 days. If you didn't expect this, you can ignore it.
  </p>
</body>
</html>
"""

_INVITE_TEXT = """\
@{inviter_username} invited you to Echo Social.

Accept your invite: https://echosocial.app/join?token={token}

This invite expires in 7 days.
"""


# ------------------------------------------------------------------ #
# Protocol
# ------------------------------------------------------------------ #


class EmailAdapter(Protocol):
    """Protocol all email adapters must satisfy."""

    async def send_invite(
        self, to: str, inviter_username: str, token: str
    ) -> None:
        """Send an invitation email. Must not raise on delivery failure."""
        ...


# ------------------------------------------------------------------ #
# Mock adapter (tests + local dev)
# ------------------------------------------------------------------ #


class MockEmailAdapter:
    """
    Logs invite details to stdout. No external calls.
    Used automatically when EMAIL_PROVIDER=mock (the default).
    """

    async def send_invite(
        self, to: str, inviter_username: str, token: str
    ) -> None:
        print(
            f"[MockEmail] Invite → to={to!r} "
            f"from=@{inviter_username} "
            f"token={token!r} "
            f"url=https://echosocial.app/join?token={token}"
        )


# ------------------------------------------------------------------ #
# Resend adapter (production)
# ------------------------------------------------------------------ #


class ResendEmailAdapter:
    """
    Production adapter using the Resend REST API.
    https://resend.com — free tier: 3,000 emails/month.

    To activate:
      1. Sign up at resend.com and get an API key
      2. Verify your sender domain (echosocial.app) in the Resend dashboard
      3. Set in .env:
           EMAIL_PROVIDER=resend
           RESEND_API_KEY=re_xxxxxxxxxxxx
           EMAIL_FROM=noreply@echosocial.app
    """

    _API_URL = "https://api.resend.com/emails"

    async def send_invite(
        self, to: str, inviter_username: str, token: str
    ) -> None:
        subject = _INVITE_SUBJECT.format(inviter_username=inviter_username)
        html = _INVITE_HTML.format(inviter_username=inviter_username, token=token)
        text = _INVITE_TEXT.format(inviter_username=inviter_username, token=token)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    self._API_URL,
                    headers={
                        "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": settings.EMAIL_FROM,
                        "to": [to],
                        "subject": subject,
                        "html": html,
                        "text": text,
                    },
                )
                resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            # Email failures are non-fatal — log and continue
            print(f"[ResendEmail] Delivery failed to {to!r}: {exc}")


# ------------------------------------------------------------------ #
# Dependency factory
# ------------------------------------------------------------------ #


def get_email_adapter() -> EmailAdapter:
    """
    FastAPI dependency — returns the adapter configured by EMAIL_PROVIDER.

    mock   → MockEmailAdapter (default; no external calls)
    resend → ResendEmailAdapter (production Resend API)
    """
    if settings.EMAIL_PROVIDER == "resend":
        return ResendEmailAdapter()
    return MockEmailAdapter()
