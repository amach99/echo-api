"""Add invites table for the Invite Friends system.

Revision ID: 002
Revises: 001
Create Date: 2026-03-19

New objects:
  - ENUM type: invite_status_enum ('pending', 'accepted', 'expired')
  - Table: invites
  - Indexes: ix_invites_token, ix_invites_inviter_id
  - Unique constraint: uq_invites_inviter_email (inviter_id, invitee_email)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # 1. ENUM TYPE
    # ------------------------------------------------------------------ #
    invite_status_enum = postgresql.ENUM(
        "pending", "accepted", "expired",
        name="invite_status_enum",
        create_type=True,
    )
    invite_status_enum.create(op.get_bind(), checkfirst=True)

    # ------------------------------------------------------------------ #
    # 2. INVITES TABLE
    # ------------------------------------------------------------------ #
    op.create_table(
        "invites",
        sa.Column(
            "invite_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "inviter_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("invitee_email", sa.Text(), nullable=False),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending", "accepted", "expired",
                name="invite_status_enum",
                create_type=False,   # already created above
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("invite_id"),
        sa.ForeignKeyConstraint(
            ["inviter_id"],
            ["users.user_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("token", name="uq_invites_token"),
        sa.UniqueConstraint(
            "inviter_id", "invitee_email", name="uq_invites_inviter_email"
        ),
    )

    # ------------------------------------------------------------------ #
    # 3. INDEXES
    # ------------------------------------------------------------------ #
    op.create_index("ix_invites_token", "invites", ["token"])
    op.create_index("ix_invites_inviter_id", "invites", ["inviter_id"])


def downgrade() -> None:
    op.drop_index("ix_invites_inviter_id", table_name="invites")
    op.drop_index("ix_invites_token", table_name="invites")
    op.drop_table("invites")

    invite_status_enum = postgresql.ENUM(
        "pending", "accepted", "expired",
        name="invite_status_enum",
        create_type=False,
    )
    invite_status_enum.drop(op.get_bind(), checkfirst=True)
