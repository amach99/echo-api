"""Add devices table for push notification token management.

Revision ID: 003
Revises: 002
Create Date: 2026-03-19

New objects:
  - ENUM type: platform_enum ('apns', 'fcm')
  - Table: devices
  - Indexes: ix_devices_token (unique), ix_devices_user_id
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # 1. ENUM TYPE
    # ------------------------------------------------------------------ #
    platform_enum = postgresql.ENUM(
        "apns", "fcm",
        name="platform_enum",
        create_type=True,
    )
    platform_enum.create(op.get_bind(), checkfirst=True)

    # ------------------------------------------------------------------ #
    # 2. DEVICES TABLE
    # ------------------------------------------------------------------ #
    op.create_table(
        "devices",
        sa.Column(
            "device_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("token", sa.String(512), nullable=False),
        sa.Column(
            "platform",
            postgresql.ENUM(
                "apns", "fcm",
                name="platform_enum",
                create_type=False,  # already created above
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("device_id"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("token", name="uq_devices_token"),
    )

    # ------------------------------------------------------------------ #
    # 3. INDEXES
    # ------------------------------------------------------------------ #
    op.create_index("ix_devices_token", "devices", ["token"])
    op.create_index("ix_devices_user_id", "devices", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_devices_user_id", table_name="devices")
    op.drop_index("ix_devices_token", table_name="devices")
    op.drop_table("devices")

    platform_enum = postgresql.ENUM(
        "apns", "fcm",
        name="platform_enum",
        create_type=False,
    )
    platform_enum.drop(op.get_bind(), checkfirst=True)
