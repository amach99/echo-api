"""tests/test_echoes.py — Human Firewall echo endpoint tests."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers
from tests.factories import create_business, create_human, create_life_post, create_pulse_post


async def test_human_can_echo_pulse_post(client: AsyncClient, db: AsyncSession) -> None:
    human = await create_human(db)
    linked = await create_human(db)
    biz = await create_business(db, linked_human=linked)
    pulse_post = await create_pulse_post(db, biz)
    await db.commit()

    resp = await client.post("/echoes",
                             json={"post_id": str(pulse_post.post_id)},
                             headers=auth_headers(human))
    assert resp.status_code == 201
    assert resp.json()["post_id"] == str(pulse_post.post_id)


async def test_business_cannot_echo(client: AsyncClient, db: AsyncSession) -> None:
    linked = await create_human(db)
    biz = await create_business(db, linked_human=linked)
    linked2 = await create_human(db)
    biz2 = await create_business(db, linked_human=linked2)
    pulse = await create_pulse_post(db, biz2)
    await db.commit()

    resp = await client.post("/echoes",
                             json={"post_id": str(pulse.post_id)},
                             headers=auth_headers(biz))
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "ECHO_REQUIRES_HUMAN_ACCOUNT"


async def test_cannot_echo_life_post(client: AsyncClient, db: AsyncSession) -> None:
    human = await create_human(db)
    author = await create_human(db)
    life = await create_life_post(db, author)
    await db.commit()

    resp = await client.post("/echoes",
                             json={"post_id": str(life.post_id)},
                             headers=auth_headers(human))
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "CANNOT_ECHO_LIFE_POST"


async def test_duplicate_echo_returns_409(client: AsyncClient, db: AsyncSession) -> None:
    human = await create_human(db)
    linked = await create_human(db)
    biz = await create_business(db, linked_human=linked)
    pulse = await create_pulse_post(db, biz)
    await db.commit()

    await client.post("/echoes", json={"post_id": str(pulse.post_id)},
                      headers=auth_headers(human))
    resp = await client.post("/echoes", json={"post_id": str(pulse.post_id)},
                             headers=auth_headers(human))
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "ALREADY_ECHOED"


async def test_delete_echo(client: AsyncClient, db: AsyncSession) -> None:
    human = await create_human(db)
    linked = await create_human(db)
    biz = await create_business(db, linked_human=linked)
    pulse = await create_pulse_post(db, biz)
    await db.commit()

    await client.post("/echoes", json={"post_id": str(pulse.post_id)},
                      headers=auth_headers(human))
    resp = await client.delete(f"/echoes/{pulse.post_id}", headers=auth_headers(human))
    assert resp.status_code == 204
