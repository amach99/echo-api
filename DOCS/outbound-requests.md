# Echo — Outbound HTTP Requests Registry
> Rule 5 compliance: All outbound HTTP calls from the backend must be documented here.
> Any new outbound integration must be added to this file before merging.

| Service | Endpoint | Purpose | Module | Data Sent |
|---|---|---|---|---|
| **Yoti Age Estimation** | `https://age.yoti.com/api/...` | Face-scan age estimation (18+ gate). Returns `{ age_verified: bool, confidence: float }` only. No biometric data transmitted to Echo. Face image deleted by Yoti immediately post-check. | `app/verification/adapter.py` | User session ID, redirect URL |
| **Yoti Age Estimation** (webhook) | Inbound callback to `POST /verification/callback` | Age estimation result delivery (inbound only). Webhook signature verified before processing. | `app/verification/router.py` | None (inbound only) |
| **AWS S3** | `https://{bucket}.s3.{region}.amazonaws.com` | Presigned PUT URL generation (media upload). Client uploads directly — Echo server never receives binary media. | `app/media/service.py` | Object key, content-type, size |

## Prohibited Outbound Destinations

The following categories of outbound connections are **prohibited** by Rule 5:
- Any third-party ad network (Meta, Google Ads, TikTok, etc.)
- Any tracking pixel service
- Any third-party analytics SDK endpoint (Mixpanel, Amplitude cloud, Heap, etc.)
- Any data broker or user profiling service

## Adding a New Outbound Integration

Before adding any new outbound HTTP call:
1. Get written approval from the Founder
2. Complete a security review via `roles/security-engineer.md`
3. Add the entry to this table
4. Document what user data (if any) is transmitted
