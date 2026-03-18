-- =============================================================================
-- PostgreSQL Schema for "Echo" Social Platform (v1.0)
-- 2026 Build-Ready Specification | Texas SB 2420 / Digital Authenticity Act
-- Source of Truth: DB Schema for Echo v1.0
-- =============================================================================
-- ARCHITECTURE NOTES:
--   Life Feed:  is_pulse_post = FALSE | sorted chronologically | Human posts only
--   Pulse Feed: is_pulse_post = TRUE  | sorted by net_score    | Business/Meme/Info
--   Human Firewall: echoes table bridges Pulse content into the Life Feed
--   ID Gate:    is_verified_human must be TRUE for ALL write-actions
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. ENUMS FOR ACCOUNT TYPES
-- -----------------------------------------------------------------------------

CREATE TYPE account_type_enum AS ENUM (
    'human',        -- Personal users. Full access to Life + Pulse.
    'business',     -- Commercial entities. Pulse only.
    'meme',         -- Curation/humor accounts. Pulse only.
    'social_info'   -- News, education, community. Pulse only.
);


-- -----------------------------------------------------------------------------
-- 2. USERS TABLE
-- Core identity table. is_verified_human is the ID Gate gatekeeper.
-- -----------------------------------------------------------------------------

CREATE TABLE users (
    user_id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    username            VARCHAR(30) UNIQUE NOT NULL,
    email               VARCHAR(255) UNIQUE NOT NULL,
    account_type        account_type_enum NOT NULL DEFAULT 'human',

    -- Texas SB 2420 / Digital Authenticity Act compliance flag.
    -- Set to TRUE only after successful Level 3 Government ID verification (Yoti/Clear).
    -- NEVER set programmatically without a verified callback from the ID provider.
    is_verified_human   BOOLEAN     DEFAULT FALSE,

    -- Internal ranking signal for Pulse Feed. NOT displayed publicly on profiles.
    -- Calculated as: SUM(upvotes) - SUM(downvotes) across all Pulse posts.
    reputation_score    INTEGER     DEFAULT 0,

    bio                 TEXT,
    profile_picture_url TEXT,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- For Business/Meme/Social Info accounts: links to the Verified Human
    -- "Representative" responsible for this account. Required for accountability.
    -- NULL for Human accounts.
    linked_human_id     UUID        REFERENCES users(user_id)
);


-- -----------------------------------------------------------------------------
-- 3. FOLLOWS TABLE (Asymmetric Social Graph)
-- A follows B does NOT imply B follows A.
-- -----------------------------------------------------------------------------

CREATE TABLE follows (
    follower_id     UUID    REFERENCES users(user_id) ON DELETE CASCADE,
    following_id    UUID    REFERENCES users(user_id) ON DELETE CASCADE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (follower_id, following_id)
);


-- -----------------------------------------------------------------------------
-- 4. POSTS TABLE
-- Unified post storage. Feed routing is determined by is_pulse_post flag.
-- -----------------------------------------------------------------------------

CREATE TABLE posts (
    post_id         UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    author_id       UUID    REFERENCES users(user_id) ON DELETE CASCADE,
    content_text    TEXT,
    media_url       TEXT,

    -- Feed routing flag.
    --   FALSE = Life Feed post  (Human account posts)
    --   TRUE  = Pulse Feed post (Business/Meme/Social Info posts)
    -- This flag is set at write-time based on the author's account_type.
    is_pulse_post   BOOLEAN DEFAULT FALSE,

    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


-- -----------------------------------------------------------------------------
-- 5. LIKES TABLE (Life Feed Interaction — Human accounts only)
-- Positive reinforcement only. No downvotes on Life Feed.
-- Only verified Human users may like. Enforced at the application layer.
-- -----------------------------------------------------------------------------

CREATE TABLE likes (
    user_id     UUID    REFERENCES users(user_id) ON DELETE CASCADE,
    post_id     UUID    REFERENCES posts(post_id) ON DELETE CASCADE,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, post_id)
);


-- -----------------------------------------------------------------------------
-- 6. VOTES TABLE (Pulse Feed Interaction — Popularity-based)
-- Upvotes (+1) and Downvotes (-1). Net score drives Pulse Feed ranking.
-- Only verified users may vote. Enforced at the application layer.
-- -----------------------------------------------------------------------------

CREATE TABLE votes (
    user_id     UUID        REFERENCES users(user_id) ON DELETE CASCADE,
    post_id     UUID        REFERENCES posts(post_id) ON DELETE CASCADE,

    -- +1 = Upvote | -1 = Downvote
    -- Net Score = SUM(vote_value) per post_id. Used for Pulse ranking only.
    vote_value  SMALLINT    CHECK (vote_value IN (1, -1)),

    created_at  TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, post_id)
);


-- -----------------------------------------------------------------------------
-- 7. ECHOES TABLE — "The Human Firewall" Bridge
-- The ONLY mechanism by which a Pulse post can appear in a Human's Life Feed.
-- echoer_id MUST reference a Human account (account_type = 'human').
-- This constraint is enforced at the application layer via middleware.
-- -----------------------------------------------------------------------------

CREATE TABLE echoes (
    -- The Human user performing the Echo/repost. Must be account_type = 'human'.
    echoer_id   UUID    REFERENCES users(user_id) ON DELETE CASCADE,
    post_id     UUID    REFERENCES posts(post_id) ON DELETE CASCADE,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (echoer_id, post_id)
);


-- -----------------------------------------------------------------------------
-- 8. MUTE_ECHOES SETTINGS
-- Granular per-friend control. Allows a user to hide a specific friend's
-- Echoed (shared) Pulse content while still seeing their original Life posts.
-- This table is checked on EVERY Life Feed query — never skipped.
-- -----------------------------------------------------------------------------

CREATE TABLE mute_echoes (
    -- The user who has applied the mute.
    user_id         UUID    REFERENCES users(user_id) ON DELETE CASCADE,

    -- The followed Human whose Echoes are being suppressed.
    muted_user_id   UUID    REFERENCES users(user_id) ON DELETE CASCADE,

    PRIMARY KEY (user_id, muted_user_id)
);


-- -----------------------------------------------------------------------------
-- INDEXES FOR PERFORMANCE
-- -----------------------------------------------------------------------------

-- Life Feed: fetch posts by author in reverse chronological order
CREATE INDEX idx_posts_chronological ON posts (author_id, created_at DESC);

-- Follow graph: look up all users that a given account is followed by
CREATE INDEX idx_follows_following ON follows (following_id);

-- Pulse Feed: look up all votes for net score calculation
CREATE INDEX idx_votes_post ON votes (post_id);

-- Echo lookup: find all echoes for a given post (used in Life Feed join)
CREATE INDEX idx_echoes_post ON echoes (post_id);

-- Mute check: quickly find all muted users for a given viewer
CREATE INDEX idx_mute_echoes_user ON mute_echoes (user_id);
