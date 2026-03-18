"""
tests/conftest.py — Shared async test fixtures.

Uses a single test PostgreSQL database that is created once per session.
Each test function runs inside a transaction that is rolled back on completion
for full isolation without dropping/recreating tables.
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.service import create_access_token
from app.config import get_settings
from app.database import get_async_db
from app.main import create_app
from app.models import Base
from app.models.user import AccountType, User
from app.redis_client import get_redis

settings = get_settings()

# Use a separate test database
_TEST_DB_URL = settings.DATABASE_URL.replace("/echo_db", "/echo_test_db")

_test_engine = create_async_engine(_TEST_DB_URL, echo=False)
_TestSessionLocal = async_sessionmaker(
    _test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_test_tables():
    """Create all tables once per test session, drop after."""
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """
    Per-test DB session. Uses a savepoint so changes are rolled back
    after each test without touching other tests' data.
    """
    async with _TestSessionLocal() as session:
        await session.begin()
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()


@pytest_asyncio.fixture
async def fake_redis():
    """In-memory Redis replacement — no real Redis needed for tests."""
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield r
    await r.aclose()


@pytest_asyncio.fixture
async def client(db: AsyncSession, fake_redis) -> AsyncGenerator[AsyncClient, None]:
    """Async test client with DB + Redis overrides."""
    app = create_app()

    async def _override_db():
        yield db

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
# Token helpers
# ------------------------------------------------------------------ #

def auth_headers(user: User) -> dict[str, str]:
    """Generate Authorization headers for a user."""
    token = create_access_token(
        user.user_id, user.is_verified_human, user.account_type.value
    )
    return {"Authorization": f"Bearer {token}"}
