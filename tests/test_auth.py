"""tests/test_auth.py — Authentication endpoint tests."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import create_human


async def test_register_human_success(client: AsyncClient, db: AsyncSession) -> None:
    resp = await client.post("/auth/register", json={
        "username": "alice", "email": "alice@test.com",
        "password": "securepass1", "account_type": "human"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


async def test_register_duplicate_username(client: AsyncClient, db: AsyncSession) -> None:
    await create_human(db, username="bob", email="bob@test.com")
    await db.commit()
    resp = await client.post("/auth/register", json={
        "username": "bob", "email": "bob2@test.com",
        "password": "securepass1", "account_type": "human"
    })
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "USERNAME_TAKEN"


async def test_register_duplicate_email(client: AsyncClient, db: AsyncSession) -> None:
    await create_human(db, username="carol", email="carol@test.com")
    await db.commit()
    resp = await client.post("/auth/register", json={
        "username": "carol2", "email": "carol@test.com",
        "password": "securepass1", "account_type": "human"
    })
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "EMAIL_TAKEN"


async def test_login_success(client: AsyncClient, db: AsyncSession) -> None:
    await create_human(db, username="dave", email="dave@test.com", password="mypassword")
    await db.commit()
    resp = await client.post("/auth/login", json={
        "email": "dave@test.com", "password": "mypassword"
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_login_wrong_password(client: AsyncClient, db: AsyncSession) -> None:
    await create_human(db, username="eve", email="eve@test.com", password="correct")
    await db.commit()
    resp = await client.post("/auth/login", json={
        "email": "eve@test.com", "password": "wrong"
    })
    assert resp.status_code == 401


async def test_me_returns_current_user(client: AsyncClient, db: AsyncSession) -> None:
    from tests.conftest import auth_headers
    user = await create_human(db, username="frank")
    await db.commit()
    resp = await client.get("/auth/me", headers=auth_headers(user))
    assert resp.status_code == 200
    assert resp.json()["username"] == "frank"


async def test_register_business_requires_linked_human(
    client: AsyncClient, db: AsyncSession
) -> None:
    resp = await client.post("/auth/register", json={
        "username": "mybiz", "email": "biz@test.com",
        "password": "securepass1", "account_type": "business",
    })
    assert resp.status_code == 422


async def test_new_user_starts_unverified(client: AsyncClient, db: AsyncSession) -> None:
    resp = await client.post("/auth/register", json={
        "username": "newuser", "email": "new@test.com",
        "password": "securepass1", "account_type": "human"
    })
    assert resp.status_code == 201
    token = resp.json()["access_token"]
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["is_verified_human"] is False
