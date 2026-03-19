# Echo — Unified Context Packet (v1.1)
> Source of Truth for all architectural decisions. Reference this file before writing any feature.
> Derived from: Echo PRD v1.0, Unified Context Packet v1.1, Building Guide, DB Schema v1.0

---

## Project Vision

A dual-feed, 18+ social ecosystem for Austin, TX (2026 Compliance). Restoring human
connection via a strictly chronological **"Life"** feed, and enabling meritocratic discovery via a
popularity-based **"Pulse"** feed.

**Core Principles:**
- 0% Algorithmic Bias
- 100% ID-Verified Humans for all write-actions
- 100% User-Controlled Content Routing

---

## 1. Account Architecture

### 1.1 Account Types (Mandatory at Sign-Up)

| Account Type | Access Level | Primary Feed | Can Post Life? | Can Post Pulse? |
|---|---|---|---|---|
| **Human User** | Full | Life Feed | ✅ Yes | ✅ Yes |
| **Business** | Restricted | Pulse Feed | ❌ No (only via Echo) | ✅ Yes |
| **Meme** | Restricted | Pulse Feed | ❌ No (only via Echo) | ✅ Yes |
| **Social Info** | Restricted | Pulse Feed | ❌ No (only via Echo) | ✅ Yes |

### 1.2 The "Texas-Standard" Age Verification (2026 Compliance — Texas SB 2420 / Digital Authenticity Act)

- **Integration**: **Yoti Age Estimation** — face scan only (no government ID required, no biometric data stored)
- **Trigger**: Required before any write-action (post, vote, echo, like, DM)
- **Gate field**: `is_verified_human = TRUE` in the `users` table
- **Verification Badge**: "Verified Human" mark is immutable once granted
- **Unverified state**: Read-only access granted; all write-actions return `HTTP 403 AGE_VERIFICATION_REQUIRED`
- **Business Linking**: Every Business/Meme/Social Info account MUST be tethered to a `linked_human_id` (a Verified Human "Representative") for legal accountability
- **Privacy guarantee**: Echo never sees, receives, or stores the user's face image, ID, or any biometric data.
  Yoti returns only `{ age_verified: bool, confidence: float }` — the face scan is deleted immediately after the check.
  Legal counsel to confirm Texas SB 2420 compliance via face-scan age estimation before public launch.

### 1.3 Rate Limiting by Account Type

| Account Type | Max Posts/Hour |
|---|---|
| Human User | 2 posts/hour |
| Business / Meme / Social Info | 5 posts/hour |

---

## 2. The Dual-Feed Logic

### 2.1 The "Life" Feed — Human Connection (The Living Room)

- **Sorting**: 100% **Chronological** (`ORDER BY created_at DESC`). No exceptions.
- **Content Source**: Only posts from **Human Users** that the viewer follows (`is_pulse_post = FALSE`)
- **Interaction**: **Likes only** (positive reinforcement; no downvotes)
- **Visual vibe**: Minimal, quiet — like old Instagram

#### The Echo Gate (Human Firewall)
Business/Meme/Social Info posts are **strictly prohibited** from appearing in the Life Feed
**unless** a Human User that the viewer follows has **"Echoed"** (reposted) that content.

```
Life Feed Query Logic:
  SELECT posts WHERE:
    (author is followed Human AND is_pulse_post = FALSE)
    UNION
    (post_id IN echoes WHERE echoer_id is followed Human
     AND echoer_id NOT IN mute_echoes for current user)
  ORDER BY effective_created_at DESC
```

#### Mute Echoes Feature
Users can toggle **"Mute Echoes"** on a **per-friend basis**:
- **Effect**: Hides that friend's Echoed (shared) Pulse content from appearing in the viewer's Life Feed
- **Does NOT affect**: The friend's original Life posts — those still appear normally
- **Implementation**: Stored in `mute_echoes` table as `(user_id, muted_user_id)` pair
- **UI**: Per-friend toggle in follow settings ("Show their Echoes: ON/OFF")

### 2.2 The "Pulse" Feed — Global Discovery (The Town Square)

- **Sorting**: **Popularity-based** — Net Score (upvotes − downvotes) + Time Decay
- **Content Source**: Global pool of Business, Meme, and Social Info posts (`is_pulse_post = TRUE`)
- **Interaction**: **Upvotes & Downvotes** (Reddit-style, `vote_value IN (1, -1)`)
- **The Meritocracy**: Content with high net scores rises; low-score content is visually dimmed
- **Visual vibe**: Dynamic, loud — net scores displayed prominently

```
Pulse Feed Query Logic:
  SELECT posts, SUM(votes.vote_value) AS net_score
  WHERE is_pulse_post = TRUE
  GROUP BY post_id
  ORDER BY net_score DESC, created_at DESC
```

#### Private Reputation Logic
- Net scores drive **internal Pulse Feed ranking** only
- Scores are **NOT displayed publicly** on user profiles
- Stored as `reputation_score` (internal field) on the `users` table

---

## 3. Core Feature Specifications

### 3.1 Echo Stories
- **Format**: 24-hour ephemeral vertical media (TTL: 24 hours from creation)
- **Human Stories**: Appear **first** in the stories tray
- **Business/Pulse Stories**: Visible only in the Pulse view, OR in Life tray if Echoed by a followed Human
- **Phase**: Implemented in Phase 2

### 3.2 Direct Messaging (DMs)
- **Human-to-Human**: Unified inbox; end-to-end encrypted (Phase 2)
- **Business-to-Human**: Routed to a separate **"Business Requests"** folder to prevent cold-DM spam
- **Human-to-Business**: Normal DM flow

### 3.3 Search & Discovery
- **Tag and User search** available to all account types
- **Pulse search results**: Ranked by All-Time Net Score
- **Phase**: Phase 2

---

## 4. Tech Stack (Canonical)

| Layer | Technology | Notes |
|---|---|---|
| Database | PostgreSQL | See `DOCS/SCHEMA.sql` |
| Backend | Python / FastAPI | ALL endpoints async |
| Auth / Age Verification | Yoti Age Estimation | Face scan only — no ID, no biometric storage |
| Media Storage | AWS S3 | Images and video |
| Feed Cache | Redis | Real-time feed caching |
| Compliance | Texas SB 2420 (2026) | Digital Authenticity Act |

---

## 5. Key Architectural Invariants

These are **non-negotiable** across every sprint and every developer:

1. A Business/Meme/Info post NEVER appears in the Life Feed without an intermediary Human Echo
2. The Life Feed is ALWAYS sorted by `created_at DESC` — never by score or engagement
3. `is_verified_human = FALSE` means read-only — no write path exists that bypasses this
4. No reputation score or net score is ever surfaced publicly on a profile page
5. The `mute_echoes` table is checked on EVERY Life Feed query — never skipped for performance

---

## 6. Age Verification Architecture

**Provider:** Yoti Age Estimation (face-scan product — distinct from Yoti Identity Verification)

Echo uses face-scan age estimation — no government ID is ever required or collected.

### Verification Flow

```
1. User taps "Verify My Age" in the app
2. App opens the Yoti Age Estimation interface (via Universal Link / deep link on mobile)
3. User performs a quick face scan (selfie) entirely within the Yoti interface
4. Yoti's on-device or server-side model estimates age
5. Face scan image is deleted immediately after the check — by Yoti's policy
6. Yoti sends a signed webhook to Echo's POST /verification/callback
7. Echo verifies the webhook signature, reads { age_verified: bool, confidence: float }
8. If age_verified = true: sets users.is_verified_human = TRUE in the database
9. User can now perform write-actions (post, like, vote, echo, follow, DM)
```

### Privacy Guarantee

| What | Echo's policy |
|---|---|
| Face image | Never transmitted to Echo. Deleted by Yoti immediately. |
| Government ID | Never requested. Not part of this flow. |
| Biometric template | Never stored by Echo or Yoti. |
| Data stored by Echo | `is_verified_human = TRUE` (boolean) + verification timestamp only. |

### Adapter Interface (Implementation Target)

```python
# app/verification/adapter.py — target interface
class AgeVerificationAdapter(Protocol):
    async def initiate_verification(self, user_id: UUID, redirect_url: str) -> str:
        """Returns the Yoti Age Estimation session URL to redirect/open for the user."""
        ...

    async def handle_callback(
        self, payload: dict, signature: str
    ) -> VerificationResult:
        """Verifies webhook signature; returns VerificationResult(age_verified, confidence)."""
        ...

# Concrete implementations:
# - YotiAgeEstimationAdapter  → production (Yoti Age Estimation API)
# - MockVerificationAdapter   → local dev (ID_VERIFY_PROVIDER=mock, auto-approves)
```

---

*Last updated: 2026-03-18 | Cross-reference: `DOCS/SCHEMA.sql`, `DOCS/ROADMAP.md`, `RULES.md`*
