"""
app/main.py — Echo API application factory.

Middleware registration order (outermost → innermost):
  SecurityHeadersMiddleware → CORSMiddleware → Routes

All routers are registered here. Write-action routers carry
`dependencies=[Depends(require_age_verified)]` at the router level.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.config import get_settings
from app.echoes.router import router as echoes_router
from app.feeds.router import router as feeds_router
from app.follows.router import router as follows_router
from app.likes.router import router as likes_router
from app.media.router import router as media_router
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.mute_echoes.router import router as mute_echoes_router
from app.posts.router import router as posts_router
from app.redis_client import close_redis, init_redis
from app.devices.router import router as devices_router
from app.invites.router import router as invites_router
from app.users.router import router as users_router
from app.verification.router import router as verification_router
from app.votes.router import router as votes_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    await init_redis()

    yield

    # Shutdown
    await close_redis()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Echo API",
        version="1.0.0",
        description=(
            "Echo — dual-feed 18+ social platform. "
            "Austin, TX market. 2026 Texas SB 2420 compliant."
        ),
        docs_url="/docs" if settings.ENV != "production" else None,
        redoc_url="/redoc" if settings.ENV != "production" else None,
        lifespan=lifespan,
    )

    # ------------------------------------------------------------------ #
    # Middleware — applied in reverse order (last added = outermost)
    # ------------------------------------------------------------------ #

    # CORS (must be before security headers so preflight works)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # Security + privacy headers (Rule 5 + Rule 6)
    app.add_middleware(SecurityHeadersMiddleware)

    # ------------------------------------------------------------------ #
    # Routers
    # ------------------------------------------------------------------ #

    # Auth — no age gate (must register/login before verifying)
    app.include_router(auth_router)

    # Feeds — read only, no age gate required
    app.include_router(feeds_router)

    # Posts — write-action gate at router level
    app.include_router(posts_router)

    # Echoes (Human Firewall) — write-action gate at router level
    app.include_router(echoes_router)

    # Follows — write-action gate at router level
    app.include_router(follows_router)

    # Likes — write-action gate at router level
    app.include_router(likes_router)

    # Votes — write-action gate at router level
    app.include_router(votes_router)

    # Mute Echoes — write-action gate at router level
    app.include_router(mute_echoes_router)

    # Media upload — write-action gate at router level
    app.include_router(media_router)

    # Devices — push token registration (all routes require auth)
    app.include_router(devices_router)

    # Invites — send + list require auth; token lookup is public
    app.include_router(invites_router)

    # Verification — /initiate requires auth; /callback is called by Yoti
    app.include_router(verification_router)

    # Users — /me requires auth; /{user_id} is public
    app.include_router(users_router)

    # ------------------------------------------------------------------ #
    # Health check (no auth)
    # ------------------------------------------------------------------ #
    @app.get("/health", tags=["system"])
    async def health() -> dict:
        return {"status": "ok", "version": "1.0.0", "env": settings.ENV}

    return app


app = create_app()
