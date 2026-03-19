"""
app/middleware/security_headers.py — Security and privacy headers (Rule 5 + Rule 6).

Implemented as raw ASGI middleware (not BaseHTTPMiddleware) to avoid anyio
task-group/event-loop conflicts with asyncpg in both production and tests.

CSP blocks all third-party scripts, images, and connections — Rule 5
(zero tracking pixels, zero ad-network integrations).
"""

from collections.abc import Callable, MutableMapping
from typing import Any

# Rule 5: CSP must block all third-party resources
_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "   # allow inline styles for Swagger UI
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "font-src 'self'; "
    "object-src 'none'; "
    "media-src 'self'; "
    "frame-ancestors 'none';"
)

_SECURITY_HEADERS: list[tuple[bytes, bytes]] = [
    (b"content-security-policy", _CSP.encode()),
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"x-xss-protection", b"1; mode=block"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (
        b"permissions-policy",
        b"geolocation=(), camera=(), microphone=(), interest-cohort=()",
    ),
]

_HSTS_HEADER = (
    b"strict-transport-security",
    b"max-age=63072000; includeSubDomains; preload",
)


class SecurityHeadersMiddleware:
    """Raw ASGI middleware that injects security headers into every HTTP response."""

    def __init__(self, app: Callable) -> None:
        self.app = app

    async def __call__(
        self,
        scope: MutableMapping[str, Any],
        receive: Callable,
        send: Callable,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        is_https = scope.get("scheme", "http") == "https"

        async def send_with_security_headers(message: MutableMapping[str, Any]) -> None:
            if message["type"] == "http.response.start":
                # Build new headers list, injecting security headers and removing "server"
                existing: list[tuple[bytes, bytes]] = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if k.lower() != b"server"          # strip server fingerprint
                ]
                new_headers = existing + _SECURITY_HEADERS
                if is_https:
                    new_headers.append(_HSTS_HEADER)
                message = {**message, "headers": new_headers}
            await send(message)

        await self.app(scope, receive, send_with_security_headers)
