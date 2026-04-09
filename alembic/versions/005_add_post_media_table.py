"""Replace posts.media_url with post_media table supporting up to 10 carousel items.

Revision ID: 005
Revises: 004
Create Date: 2026-04-09

Changes:
  - New table: post_media (media_id PK, post_id FK→posts, media_url, position, created_at)
  - Data migration: existing posts.media_url rows → post_media at position 0
  - Drop column: posts.media_url
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # CREATE post_media TABLE
    # ------------------------------------------------------------------ #
    op.create_table(
        "post_media",
        sa.Column(
            "media_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("post_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("media_url", sa.Text, nullable=False),
        sa.Column("position", sa.Integer, server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("media_id"),
        sa.ForeignKeyConstraint(
            ["post_id"], ["posts.post_id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_post_media_post_id", "post_media", ["post_id"])

    # ------------------------------------------------------------------ #
    # MIGRATE existing single media_url values → post_media at position 0
    # ------------------------------------------------------------------ #
    op.execute(
        """
        INSERT INTO post_media (post_id, media_url, position)
        SELECT post_id, media_url, 0
        FROM posts
        WHERE media_url IS NOT NULL
        """
    )

    # ------------------------------------------------------------------ #
    # DROP the now-redundant column from posts
    # ------------------------------------------------------------------ #
    op.drop_column("posts", "media_url")


def downgrade() -> None:
    # Re-add media_url column (nullable — multi-image posts will lose items 1+)
    op.add_column("posts", sa.Column("media_url", sa.Text, nullable=True))

    # Restore the first (position=0) media_url back onto each post
    op.execute(
        """
        UPDATE posts p
        SET media_url = pm.media_url
        FROM post_media pm
        WHERE p.post_id = pm.post_id
          AND pm.position = 0
        """
    )

    op.drop_index("ix_post_media_post_id", table_name="post_media")
    op.drop_table("post_media")
