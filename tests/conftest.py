"""
tests/conftest.py — Shared async test fixtures.

Architecture:
- asyncio_default_fixture_loop_scope = "session" (pyproject.toml) gives all
  async fixtures and tests one shared session event loop, avoiding asyncpg
  "Future attached to a different loop" errors.
- Tables are created once per session via test_engine (session fixture).
- Two-session design for test isolation:
    * `db`     — test-side session for seeding data; tests must call
                 `await db.commit()` before making HTTP requests so the
                 app's separate connection can see the committed rows.
    * `client` — FastAPI app gets its OWN fresh session per request
                 (not the same connection as `db`) to avoid asyncpg
                 "another operation is in progress" single-connection limits.
- Tables persist within a session (committed data accumulates), but every
  test uses unique identifiers so there are no intra-session conflicts.
  The session-teardown `drop_all` wipes everything between pytest runs.
"""

from collections.abc import AsyncGenerator

import fakeredis.aioredis
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.service import create_access_token
from app.config import get_settings
from app.database import get_async_db
from app.main import create_app
from app.models import Base
from app.models.user import User
from app.redis_client import get_redis

settings = get_settings()

# Separate test database — never touch echo_db
_TEST_DB_URL = settings.DATABASE_URL.replace("/echo_db", "/echo_test_db")


# ------------------------------------------------------------------ #
# Session-scoped engine + tables
# ------------------------------------------------------------------ #

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Session-scoped SQLAlchemy async engine (one asyncpg pool for all tests)."""
    # NullPool: each session gets its own connection; no pool state bleed between tests
    engine = create_async_engine(_TEST_DB_URL, echo=False, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def test_session_factory(test_engine):
    """Session-scoped session factory sharing the session-scoped engine."""
    yield async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


# ------------------------------------------------------------------ #
# Per-test DB session (test-side seeding only)
# ------------------------------------------------------------------ #

@pytest_asyncio.fixture
async def db(test_session_factory) -> AsyncGenerator[AsyncSession, None]:
    """
    Per-test DB session for seeding data.

    IMPORTANT: If you create rows here and need the HTTP client to see them,
    call `await db.commit()` before making any requests. The FastAPI app uses
    a separate connection and can only see committed rows.

    Uncommitted work is rolled back on teardown so in-progress state is cleaned.
    """
    async with test_session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()


# ------------------------------------------------------------------ #
# Redis + HTTP client
# ------------------------------------------------------------------ #

@pytest_asyncio.fixture
async def fake_redis():
    """In-memory Redis replacement — no real Redis needed for tests."""
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield r
    await r.aclose()


@pytest_asyncio.fixture
async def client(test_session_factory, fake_redis) -> AsyncGenerator[AsyncClient, None]:
    """
    Async test client. The FastAPI app gets its own fresh session per request
    from test_session_factory — completely separate from the test's `db` session.
    This avoids asyncpg's single-operation-per-connection limit when the test
    body and the HTTP handler would otherwise share a connection.
    """
    app = create_app()

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        """
        Fresh session per FastAPI request, pointed at echo_test_db.
        Mirrors production get_async_db: commit on success, rollback on error.
        """
        async with test_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def _override_redis():
        yield fake_redis

    app.dependency_overrides[get_async_db] = _override_db
    app.dependency_overrides[get_redis] = _override_redis

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ------------------------------------------------------------------ #
# Token helper (sync — safe to call from any async test)
# ------------------------------------------------------------------ #

def auth_headers(user: User) -> dict[str, str]:
    """Generate Authorization: Bearer headers for a given user."""
    token = create_access_token(
        user.user_id, user.is_verified_human, user.account_type.value
    )
    return {"Authorization": f"Bearer {token}"}
