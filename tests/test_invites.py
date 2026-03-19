"""tests/test_invites.py — Invite Friends system tests."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers
from tests.factories import create_human


# ------------------------------------------------------------------ #
# POST /invites — send an invite
# ------------------------------------------------------------------ #


async def test_send_invite_success(client: AsyncClient, db: AsyncSession) -> None:
    inviter = await create_human(db)
    await db.commit()

    resp = await client.post(
        "/invites",
        json={"invitee_email": "friend@example.com"},
        headers=auth_headers(inviter),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["invitee_email"] == "friend@example.com"
    assert data["status"] == "pending"
    assert "token" in data
    assert len(data["token"]) >= 32  # secrets.token_urlsafe(32)
    assert "invite_id" in data
    assert "expires_at" in data


async def test_send_invite_requires_auth(client: AsyncClient, db: AsyncSession) -> None:
    resp = await client.post(
        "/invites",
        json={"invitee_email": "friend@example.com"},
    )
    assert resp.status_code == 401


async def test_send_duplicate_invite_returns_409(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Same inviter + same email while first invite is still pending → 409."""
    inviter = await create_human(db)
    await db.commit()

    await client.post(
        "/invites",
        json={"invitee_email": "friend@example.com"},
        headers=auth_headers(inviter),
    )
    resp = await client.post(
        "/invites",
        json={"invitee_email": "friend@example.com"},
        headers=auth_headers(inviter),
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "INVITE_ALREADY_SENT"


async def test_different_inviters_can_invite_same_email(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Two different users can each invite the same email address."""
    inviter1 = await create_human(db)
    inviter2 = await create_human(db)
    await db.commit()

    resp1 = await client.post(
        "/invites",
        json={"invitee_email": "shared@example.com"},
        headers=auth_headers(inviter1),
    )
    resp2 = await client.post(
        "/invites",
        json={"invitee_email": "shared@example.com"},
        headers=auth_headers(inviter2),
    )
    assert resp1.status_code == 201
    assert resp2.status_code == 201


# ------------------------------------------------------------------ #
# GET /invites/me — list sent invites
# ------------------------------------------------------------------ #


async def test_get_my_invites_empty(client: AsyncClient, db: AsyncSession) -> None:
    user = await create_human(db)
    await db.commit()

    resp = await client.get("/invites/me", headers=auth_headers(user))
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_my_invites_shows_sent(
    client: AsyncClient, db: AsyncSession
) -> None:
    inviter = await create_human(db)
    await db.commit()

    await client.post(
        "/invites",
        json={"invitee_email": "buddy@example.com"},
        headers=auth_headers(inviter),
    )
    resp = await client.get("/invites/me", headers=auth_headers(inviter))
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["invitee_email"] == "buddy@example.com"
    assert items[0]["status"] == "pending"


async def test_get_my_invites_requires_auth(
    client: AsyncClient, db: AsyncSession
) -> None:
    resp = await client.get("/invites/me")
    assert resp.status_code == 401


# ------------------------------------------------------------------ #
# GET /invites/{token} — validate token (public)
# ------------------------------------------------------------------ #


async def test_validate_token_success(client: AsyncClient, db: AsyncSession) -> None:
    inviter = await create_human(db)
    await db.commit()

    send_resp = await client.post(
        "/invites",
        json={"invitee_email": "newuser@example.com"},
        headers=auth_headers(inviter),
    )
    token = send_resp.json()["token"]

    resp = await client.get(f"/invites/{token}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["inviter_username"] == inviter.username
    assert data["invitee_email"] == "newuser@example.com"
    assert "expires_at" in data


async def test_validate_invalid_token_returns_404(
    client: AsyncClient, db: AsyncSession
) -> None:
    resp = await client.get(f"/invites/{secrets.token_urlsafe(32)}")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "INVITE_NOT_FOUND"


async def test_validate_accepted_token_returns_410(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Token that was already accepted via registration → 410."""
    from sqlalchemy import select
    from app.models.invite import Invite, InviteStatus

    inviter = await create_human(db)
    await db.commit()

    send_resp = await client.post(
        "/invites",
        json={"invitee_email": "accepted@example.com"},
        headers=auth_headers(inviter),
    )
    token = send_resp.json()["token"]

    # Directly flip status to accepted in DB (simulates post-registration state)
    result = await db.execute(select(Invite).where(Invite.token == token))
    invite = result.scalar_one()
    invite.status = InviteStatus.ACCEPTED
    invite.accepted_at = datetime.now(UTC)
    await db.commit()

    resp = await client.get(f"/invites/{token}")
    assert resp.status_code == 410
    assert resp.json()["detail"]["code"] == "INVITE_EXPIRED"


# ------------------------------------------------------------------ #
# Registration hook
# ------------------------------------------------------------------ #


async def test_register_with_valid_invite_marks_accepted(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Registering with a valid invite_token flips invite.status to accepted."""
    from sqlalchemy import select
    from app.models.invite import Invite, InviteStatus

    inviter = await create_human(db)
    await db.commit()

    send_resp = await client.post(
        "/invites",
        json={"invitee_email": "newbie@example.com"},
        headers=auth_headers(inviter),
    )
    token = send_resp.json()["token"]

    reg_resp = await client.post(
        "/auth/register",
        json={
            "username": "newbie_user",
            "email": "newbie@example.com",
            "password": "securepassword1",
            "invite_token": token,
        },
    )
    assert reg_resp.status_code == 201

    # Verify invite is now accepted
    result = await db.execute(select(Invite).where(Invite.token == token))
    invite = result.scalar_one()
    await db.refresh(invite)
    assert invite.status == InviteStatus.ACCEPTED
    assert invite.accepted_at is not None


async def test_register_with_invalid_invite_still_succeeds(
    client: AsyncClient, db: AsyncSession
) -> None:
    """A bad invite_token never blocks registration — silently ignored."""
    resp = await client.post(
        "/auth/register",
        json={
            "username": "independent_user",
            "email": "independent@example.com",
            "password": "securepassword1",
            "invite_token": "totally-invalid-token",
        },
    )
    assert resp.status_code == 201
