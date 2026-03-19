"""tests/test_verification.py — Age verification endpoint tests."""

import json
import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers
from tests.factories import create_unverified_user, create_human


async def test_initiate_verification_requires_auth(
    client: AsyncClient, db: AsyncSession
) -> None:
    resp = await client.post("/verification/initiate")
    assert resp.status_code == 401


async def test_initiate_verification_success(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Mock adapter returns a fake Yoti URL."""
    user = await create_human(db)
    await db.commit()

    resp = await client.post("/verification/initiate", headers=auth_headers(user))
    assert resp.status_code == 201
    data = resp.json()
    assert "session_url" in data
    assert data["session_url"].startswith("https://mock.yoti.test/verify/")
    assert "message" in data


async def test_callback_mock_sets_verified(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Mock adapter always approves — user.is_verified_human should flip to True."""
    user = await create_unverified_user(db)
    await db.commit()

    payload = {
        "session_id": str(uuid.uuid4()),
        "user_tracking_id": str(user.user_id),
        "topic": "SESSION_COMPLETION",
    }
    resp = await client.post(
        "/verification/callback",
        content=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["age_verified"] == "true"

    # Reload user from DB to confirm the flag was persisted
    await db.refresh(user)
    assert user.is_verified_human is True


async def test_callback_missing_session_id_returns_400(
    client: AsyncClient, db: AsyncSession
) -> None:
    resp = await client.post(
        "/verification/callback",
        content=json.dumps({"topic": "SESSION_COMPLETION"}),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "MISSING_FIELDS"


async def test_callback_missing_user_tracking_id_returns_400(
    client: AsyncClient, db: AsyncSession
) -> None:
    resp = await client.post(
        "/verification/callback",
        content=json.dumps({"session_id": "sess_abc", "topic": "SESSION_COMPLETION"}),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "MISSING_FIELDS"


async def test_callback_invalid_user_id_returns_400(
    client: AsyncClient, db: AsyncSession
) -> None:
    resp = await client.post(
        "/verification/callback",
        content=json.dumps(
            {
                "session_id": "sess_abc",
                "user_tracking_id": "not-a-uuid",
                "topic": "SESSION_COMPLETION",
            }
        ),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "INVALID_USER_ID"
