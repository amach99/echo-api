"""Add comments table for threaded post comments.

Revision ID: 004
Revises: 003
Create Date: 2026-03-19

New objects:
  - Table: comments
  - Self-referential FK: comments.parent_id → comments.comment_id
  - Indexes: ix_comments_post_id, ix_comments_author_id, ix_comments_parent_id
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # COMMENTS TABLE
    # ------------------------------------------------------------------ #
    op.create_table(
        "comments",
        sa.Column(
            "comment_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "post_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("comment_id"),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["posts.post_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.user_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["comments.comment_id"],
            ondelete="CASCADE",
        ),
    )

    # ------------------------------------------------------------------ #
    # INDEXES
    # ------------------------------------------------------------------ #
    op.create_index("ix_comments_post_id", "comments", ["post_id"])
    op.create_index("ix_comments_author_id", "comments", ["author_id"])
    op.create_index("ix_comments_parent_id", "comments", ["parent_id"])


def downgrade() -> None:
    op.drop_index("ix_comments_parent_id", table_name="comments")
    op.drop_index("ix_comments_author_id", table_name="comments")
    op.drop_index("ix_comments_post_id", table_name="comments")
    op.drop_table("comments")
