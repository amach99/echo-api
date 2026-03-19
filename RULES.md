# Echo — RULES.md
## Primary Behavioral Constraint for All Coding Tasks
> Authored by: Backend Architect persona | Security Engineer review
> Version: 2.0 (PRD-informed) | Platform: Echo Social (Austin, TX) | Compliance: 2026
> Cross-reference: `DOCS/CONTEXT_PACKET.md`, `DOCS/SCHEMA.sql`, `DOCS/ROADMAP.md`

These rules are **non-negotiable**. Any PR that violates them is auto-rejected.
Any exception requires written Founder approval + Security Engineer sign-off in `DOCS/exceptions/`.

---

## RULE 1 — Zero Algorithmic Influence

### Life Feed: Strictly Chronological
- Content in the Life Feed MUST be sorted `ORDER BY created_at DESC` and nothing else.
- **Prohibited**: engagement scoring, personalization models, ML ranking, A/B content experiments, recency-weighted blending, or any signal other than `created_at`.

### Pulse Feed: Community Net-Score Only
- Content in the Pulse Feed MUST be sorted by net score (`SUM(vote_value)`) then by `created_at DESC` as a tiebreaker.
- **Prohibited**: platform-applied boosts, advertiser priority, engagement-rate weighting, time-decay curves beyond the raw timestamp tiebreaker, or any ML inference.

```python
# ONLY ALLOWED sort strategies — enforced via Literal type
FeedSortStrategy = Literal["chronological", "net_score"]

# Life Feed query (canonical form)
# SELECT ... WHERE is_pulse_post = FALSE AND author_id IN (followed_human_ids)
#   UNION echoed posts by followed humans (filtered by mute_echoes)
# ORDER BY effective_timestamp DESC

# Pulse Feed query (canonical form)
# SELECT post_id, SUM(vote_value) AS net_score
# WHERE is_pulse_post = TRUE
# GROUP BY post_id
# ORDER BY net_score DESC, created_at DESC
```

---

## RULE 2 — 2026 Texas Compliance: Mandatory 18+ Age Verification

### Legal Basis
Texas SB 2420 (2026) / Digital Authenticity Act.
No anonymous write-access. Period.

### Technical Enforcement
- Every endpoint that creates, modifies, or deletes user-generated content MUST pass through `AgeVerificationMiddleware` before the handler executes.
- The middleware verifies `users.is_verified_human == True` on the authenticated user's token claim on **every** write request.
- Unverified users receive: `HTTP 403 FORBIDDEN` with body `{"code": "AGE_VERIFICATION_REQUIRED"}`.

```python
# Required pattern — applied at router level for ALL write-action routers
from fastapi import APIRouter, Depends
from app.middleware.age_verification import require_age_verified

# Every write-action router MUST declare this dependency
router = APIRouter(dependencies=[Depends(require_age_verified)])

# Write-actions covered (non-exhaustive):
#   POST /posts         — creating a post
#   POST /likes         — liking a post
#   POST /votes         — voting on a Pulse post
#   POST /echoes        — echoing a Pulse post into Life feed
#   POST /follows       — following a user
#   DELETE /follows     — unfollowing
#   POST /dms           — sending a direct message
#   POST /mute-echoes   — muting a user's echoes
```

### Prohibited Bypasses
- No admin override flags that skip age verification in staging/production
- No feature flags that disable this check outside of local `ENV=development`
- No test-mode shortcuts in any deployed environment
- No backdoor endpoints that accept `bypass_verification=true`
- **No storage of face images, government IDs, or biometric templates at any layer**
  (API server, database, S3, Redis, application logs)
- **No logging of raw verification webhook payloads** if they contain biometric data

### ID Verification Method: Yoti Age Estimation (Face Scan Only)

- **Provider:** Yoti Age Estimation — face scan product, not Yoti Identity Verification (no government ID required)
- **Method:** Face scan (selfie) only. No document upload. No biometric template stored anywhere.
- **No Data Storage:** Echo never sees, receives, or stores your ID, photo, or biometric data.
  Yoti performs age estimation and returns only a boolean result (`age ≥ 18: yes/no`) and a
  confidence score. The face scan image is deleted immediately after the check is complete.
  Yoti does not retain biometric data — confirmed by Yoti's published data policy.
- On successful callback: set `users.is_verified_human = TRUE` via trusted server-side call only.
- Never accept client-submitted `is_verified_human` values.
- **Legal note:** Texas SB 2420 / Digital Authenticity Act compliance via face-scan age estimation
  is to be confirmed by legal counsel before public launch. Development proceeds on this model.

---

## RULE 3 — Human Firewall Enforcement

### The Law of the Life Feed
Business/Meme/Social Info content is **strictly prohibited** from appearing in a Human user's
Life Feed **unless** it has been explicitly "Echoed" by a Human User that the viewer follows.

```python
# The Human Firewall: enforced at write-time AND query-time

# Write-time: only Human accounts can create Echo rows
async def create_echo(echoer: User, post_id: UUID, db: AsyncSession) -> Echo:
    if echoer.account_type != AccountType.HUMAN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ECHO_REQUIRES_HUMAN_ACCOUNT"}
        )
    if not echoer.is_verified_human:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "AGE_VERIFICATION_REQUIRED"}
        )
    # Proceed to insert into echoes table
    ...

# Query-time: Life Feed only includes Business content via the echoes join
# Any Life Feed query that omits the echoes filter is a CRITICAL bug
```

### Business → Life Feed Pathway (The Only Allowed Path)
```
Business/Meme/Info publishes post (is_pulse_post = TRUE)
    → Post lives in Pulse Feed ✅
    → Human User (verified) Echoes the post
        → Echo row created: (echoer_id, post_id)
        → Post now visible in followers' Life Feeds
            (unless viewer has muted that Human's Echoes)
```

### Mute Echoes
- The `mute_echoes` table MUST be consulted on every Life Feed query.
- Skipping the mute check for performance reasons is a **critical bug** — fix it, don't bypass it.

---

## RULE 4 — Async-First FastAPI

- Every FastAPI route handler MUST be declared `async def`.
- All database operations use `asyncpg` or SQLAlchemy async session (`AsyncSession`).
- All HTTP calls use `httpx.AsyncClient`.
- All file I/O uses `aiofiles`.
- CPU-bound work (image processing, etc.) must be offloaded via `asyncio.get_event_loop().run_in_executor()`.

```python
# CORRECT ✅
@router.post("/posts", status_code=201)
async def create_post(
    payload: PostCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> PostResponse:
    ...

# REJECTED ❌ — sync handler, will not be merged
@router.post("/posts", status_code=201)
def create_post(payload: PostCreate, db: Session = Depends(get_db)):
    ...
```

---

## RULE 5 — Zero Third-Party Tracking

- **No tracking pixels** (1×1 images, beacon requests, conversion tags, etc.)
- **No third-party ad-network integrations** (Meta Pixel, Google Ads, TikTok Pixel, etc.)
- **No third-party analytics SDKs** that exfiltrate user behavior to external services
- **First-party analytics only** — self-hosted, zero data-sharing agreements with ad networks
- All outbound HTTP calls from the backend must be catalogued in `DOCS/outbound-requests.md`

```python
# Content-Security-Policy header enforced on all responses
CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none';"
)
```

---

## RULE 6 — Security Baselines

- **Authentication**: JWT with access tokens ≤15 min lifetime + refresh token rotation
- **Authorization**: RBAC enforced at service layer, not just API gateway
- **Input validation**: All inputs validated with Pydantic v2 `BaseModel` — no raw dict access
- **SQL**: Parameterized queries only via ORM — no raw string interpolation
- **Secrets**: Environment variables or secrets manager — never committed to source
- **Rate limiting**: Per-IP and per-user limits on all public endpoints (see PRD §4 for values)
- **Dependency scanning**: `pip-audit` runs in CI on every PR; CRITICAL/HIGH findings block merge
- **Encryption at rest**: All user data encrypted at rest in PostgreSQL

---

## RULE 7 — Feed Integrity Testing (Mandatory Before Any Release)

The following tests MUST pass before any backend deployment:

1. **Firewall test**: POST as a Business account directly to Life Feed → must return `403`
2. **Verification test**: Attempt any write action with `is_verified_human = False` → must return `403`
3. **Sort test**: Life Feed response array is sorted strictly by `created_at DESC` with no gaps
4. **Echo test**: Echo a Business post as a Human → appears in follower's Life Feed
5. **Mute test**: Mute that Human's Echoes → Echoed post disappears from Life Feed

---

## Quick Reference Card

| Rule | Summary | Violation Severity |
|---|---|---|
| Rule 1 | No algorithmic sorting — chrono or net-score only | CRITICAL |
| Rule 2 | 18+ age gate on all write-actions — face scan, no biometric storage (Texas SB 2420) | CRITICAL |
| Rule 3 | Business content in Life Feed only via Human Echo | CRITICAL |
| Rule 4 | All FastAPI endpoints must be `async def` | HIGH |
| Rule 5 | Zero third-party tracking pixels or ad networks | CRITICAL |
| Rule 6 | Standard security baselines | HIGH |
| Rule 7 | Firewall + verification tests must pass pre-deploy | HIGH |

---

## Roles Reference
- `roles/backend-architect.md` — system design, API structure, database architecture
- `roles/security-engineer.md` — threat modeling, secure code review, compliance hardening
