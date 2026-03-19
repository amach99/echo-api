# Echo — Product Roadmap
> Source: PRD v1.0 + Unified Context Packet v1.1
> Market: Austin, TX | Compliance target: 2026 (Texas SB 2420 / Digital Authenticity Act)

---

## Phase 1: The MVP — "The Foundation"
**Goal: Launch the core "Human vs. Business" loop in the Austin market.**

This phase establishes the non-negotiable infrastructure that every future feature depends on.
Nothing moves to Phase 2 until all five Phase 1 milestones pass security review.

---

### Milestone 1.1 — Identity Core (The 18+ Age Gate)
**This is the make-or-break milestone. Everything else is blocked until this is production-ready.**

- [ ] Integrate **Yoti Age Estimation** API for face-scan age verification (no government ID — no biometric storage)
- [ ] Implement age-check callback that sets `users.is_verified_human = TRUE` on success
- [ ] Build `AgeVerificationMiddleware` — applied as a FastAPI `Depends` on **all write-action routes**
  - POST /posts
  - POST /likes
  - POST /votes
  - POST /echoes
  - POST /follows
  - POST /dms
- [ ] Enforce read-only state for unverified users (`HTTP 403 AGE_VERIFICATION_REQUIRED`)
- [ ] Build mock verification flow (Yoti/Clear placeholder) for local development
- [ ] Write integration tests: verify no write endpoint is reachable with `is_verified_human = FALSE`

**Compliance reference**: Texas SB 2420 (2026) / Digital Authenticity Act

---

### Milestone 1.2 — The Dual Switch (Feed Routing Logic)
**The core product differentiation. Life and Pulse must be treated as completely separate query paths.**

#### Life Feed
- [ ] Query engine: `posts WHERE is_pulse_post = FALSE AND author_id IN (followed Human users)`
- [ ] Sort: `ORDER BY created_at DESC` — strictly chronological, zero exceptions
- [ ] Interaction: Likes endpoint (Human accounts only, verified only)
- [ ] Apply `mute_echoes` filter on every Life Feed query

#### Pulse Feed
- [ ] Query engine: `posts WHERE is_pulse_post = TRUE` joined with `votes` for net score
- [ ] Sort: `ORDER BY net_score DESC, created_at DESC` (net score = SUM of vote_value per post)
- [ ] Interaction: Upvote/Downvote endpoints (verified users only)
- [ ] Visual: Net score displayed on each Pulse card; low-score posts visually dimmed

#### Feed Routing at Write-Time
- [ ] On post creation: set `is_pulse_post` automatically based on `author.account_type`
  - `human` → `is_pulse_post = FALSE`
  - `business`, `meme`, `social_info` → `is_pulse_post = TRUE`

---

### Milestone 1.3 — The Human Firewall (Echo Bridge)
**The mechanism that keeps Business content out of the Life Feed unless humans vouch for it.**

- [ ] Echo endpoint: `POST /echoes` — creates row in `echoes` table
  - Validate: `echoer.account_type == 'human'` (only Humans can Echo)
  - Validate: `echoer.is_verified_human == True`
  - Validate: target post `is_pulse_post == True` (no need to Echo Life posts)
- [ ] Life Feed query: `UNION` with echoes by followed Humans, filtered by `mute_echoes`
- [ ] Un-echo endpoint: `DELETE /echoes/{post_id}` — removes the bridge row
- [ ] Test: Attempt to POST as Business directly to Life Feed → must fail with `403 FORBIDDEN`
- [ ] Test: Echo a Business post as a Human → must appear in follower's Life Feed
- [ ] Test: Mute that Human's Echoes → Echoed Business post must disappear from Life Feed

---

### Milestone 1.4 — Basic Social Graph
**The table stakes for any social platform.**

- [ ] Follow / Unfollow endpoints (`POST /follows`, `DELETE /follows/{user_id}`)
- [ ] Media posting: Photo and Video upload to AWS S3; `media_url` stored on `posts`
- [ ] Business account registration flow with `linked_human_id` requirement
- [ ] User profile pages (read-only reputation score — internal only, not displayed)

---

### Milestone 1.5 — Mute Echoes (Granular Life Feed Control)
**Gives users fine-grained control over what enters their living room.**

- [ ] Mute Echoes toggle: `POST /mute-echoes/{user_id}` / `DELETE /mute-echoes/{user_id}`
- [ ] Persists to `mute_echoes` table
- [ ] Life Feed query respects mute list on every request
- [ ] UI: Per-friend toggle accessible from the follow settings screen

---

## Phase 2: Engagement & Scale — "The Scale Up"
**Goal: Deepen engagement and build community tools.**

| Feature | Description |
|---|---|
| **Echo Stories** | 24-hour ephemeral vertical media pipeline (TTL-based expiry). Human stories prioritized in tray. |
| **Verified Representative Links** | Show the "Face" (linked Human profile) behind each Business account in Pulse. |
| **Encrypted DMs** | End-to-end encryption for Human-to-Human messaging. "Business Requests" folder live in Phase 1 MVP. |
| **Global Search** | Tag-based discovery for Pulse feed, ranked by All-Time Net Score. |
| **Reputation Scoring Display** | Show per-user Pulse vote history on their own private profile dashboard (not publicly). |

---

## Phase 3: Future Expansion — "Stored for Implementation"
**Long-term vision. Not on the active build schedule.**

| Feature | Description |
|---|---|
| **The Town Square** | Hyper-local geofenced feed for Austin/Leander neighborhoods. |
| **Echo Marketplace** | Business direct-to-consumer sales within Pulse posts. Human-vetted listings. |

---

## Build Order Rationale (from Building Guide)

Follow this sequence strictly — do not parallelize across phases:

```
1. Base Layer (DB + Schema)       ← DOCS/SCHEMA.sql
2. ID Gate (18+ Middleware)       ← Milestone 1.1
3. Feed Routing Logic (API)       ← Milestones 1.2 + 1.3
4. Basic Social                   ← Milestone 1.4
5. Mute Echoes                    ← Milestone 1.5
6. Sleek UI (Frontend)            ← After all backend milestones pass
```

> "Test the Firewall": Once a basic version exists, attempt to post as a Business account
> directly to a Human's Life feed. If it succeeds, that is a critical bug. Fix before advancing.

---

*Cross-reference: `DOCS/CONTEXT_PACKET.md`, `DOCS/SCHEMA.sql`, `RULES.md`*
