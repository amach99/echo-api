"""Initial schema — all Echo tables v1.0

Revision ID: 001
Revises:
Create Date: 2026-03-18

Matches DOCS/SCHEMA.sql exactly.
Tables: users, follows, posts, likes, votes, echoes, mute_echoes
Indexes: idx_posts_chronological, idx_follows_following,
         idx_votes_post, idx_echoes_post, idx_mute_echoes_user
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # 1. ENUM TYPE
    # ------------------------------------------------------------------ #
    account_type_enum = postgresql.ENUM(
        "human", "business", "meme", "social_info",
        name="account_type_enum",
        create_type=True,
    )
    account_type_enum.create(op.get_bind(), checkfirst=True)

    # ------------------------------------------------------------------ #
    # 2. USERS TABLE
    # ------------------------------------------------------------------ #
    op.create_table(
        "users",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("username", sa.String(30), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column(
            "account_type",
            postgresql.ENUM(
                "human", "business", "meme", "social_info",
                name="account_type_enum",
                create_type=False,
            ),
            server_default="human",
            nullable=False,
        ),
        sa.Column(
            "is_verified_human",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "reputation_score",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("profile_picture_url", sa.Text(), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "linked_human_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["linked_human_id"], ["users.user_id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("email"),
    )

    # ------------------------------------------------------------------ #
    # 3. FOLLOWS TABLE
    # ------------------------------------------------------------------ #
    op.create_table(
        "follows",
        sa.Column("follower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("following_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["follower_id"], ["users.user_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["following_id"], ["users.user_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("follower_id", "following_id"),
    )

    # ------------------------------------------------------------------ #
    # 4. POSTS TABLE
    # ------------------------------------------------------------------ #
    op.create_table(
        "posts",
        sa.Column(
            "post_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("media_url", sa.Text(), nullable=True),
        sa.Column(
            "is_pulse_post",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["author_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("post_id"),
    )

    # ------------------------------------------------------------------ #
    # 5. LIKES TABLE
    # ------------------------------------------------------------------ #
    op.create_table(
        "likes",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("post_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["post_id"], ["posts.post_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "post_id"),
    )

    # ------------------------------------------------------------------ #
    # 6. VOTES TABLE
    # ------------------------------------------------------------------ #
    op.create_table(
        "votes",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("post_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vote_value", sa.SmallInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("vote_value IN (1, -1)", name="ck_vote_value"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["post_id"], ["posts.post_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "post_id"),
    )

    # ------------------------------------------------------------------ #
    # 7. ECHOES TABLE — "The Human Firewall" Bridge
    # ------------------------------------------------------------------ #
    op.create_table(
        "echoes",
        sa.Column("echoer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("post_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["echoer_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["post_id"], ["posts.post_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("echoer_id", "post_id"),
    )

    # ------------------------------------------------------------------ #
    # 8. MUTE_ECHOES TABLE
    # ------------------------------------------------------------------ #
    op.create_table(
        "mute_echoes",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("muted_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["muted_user_id"], ["users.user_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "muted_user_id"),
    )

    # ------------------------------------------------------------------ #
    # INDEXES (from DOCS/SCHEMA.sql + additional for Pulse/Echo/Mute queries)
    # ------------------------------------------------------------------ #
    op.create_index(
        "idx_posts_chronological", "posts", ["author_id", sa.text("created_at DESC")]
    )
    op.create_index("idx_follows_following", "follows", ["following_id"])
    op.create_index("idx_votes_post", "votes", ["post_id"])
    op.create_index("idx_echoes_post", "echoes", ["post_id"])
    op.create_index("idx_mute_echoes_user", "mute_echoes", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_mute_echoes_user", table_name="mute_echoes")
    op.drop_index("idx_echoes_post", table_name="echoes")
    op.drop_index("idx_votes_post", table_name="votes")
    op.drop_index("idx_follows_following", table_name="follows")
    op.drop_index("idx_posts_chronological", table_name="posts")

    op.drop_table("mute_echoes")
    op.drop_table("echoes")
    op.drop_table("votes")
    op.drop_table("likes")
    op.drop_table("posts")
    op.drop_table("follows")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS account_type_enum")
