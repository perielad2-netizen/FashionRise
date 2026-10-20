# FashionRise — Origin Access JWT implementation notes

**Status:** draft code PR — **default disabled**. Not deployed. Not Stage D authorization.  
**Design:** `docs/deploy/WEB-V3B-ORIGIN-ACCESS-JWT-DESIGN.md`  
**Modules:** `backend/app/core/cloudflare_access.py`, `cloudflare_access_middleware.py`

## Coverage boundary (accurate)

| Surface | Protected by this middleware? | Remaining controls |
|---|---|---|
| FastAPI `/api/**` (after path normalization) | **Yes**, when `CF_ACCESS_JWT_VALIDATION=true` | FashionRise app JWT / ownership deps unchanged |
| `GET /health` | **No** (explicit exemption) | Loopback bind `127.0.0.1:8010`; not an Access identity check |
| Other non-`/api` FastAPI paths (e.g. `/ready`, `/static/uploads`) | **No** — outside API gate | Must not be exposed publicly by Nginx; loopback / existing deny rules |
| Nginx static HTML (`/`, `/index.html`, `/sw.js`, `/assets/**`) | **No** — never reaches FastAPI | Edge Cloudflare Access + FashionRise-private AOP |

**Do not claim origin-wide Access JWT enforcement** from this middleware alone.

## Assertion header policy

- Header-only: `Cf-Access-Jwt-Assertion` (case-insensitive). **No cookie fallback**.
- Reject any duplicate field (identical or empty), any comma (leading/trailing/joined), whitespace padding, and non-compact-JWS shapes → generic `403`.

## JWKS reliability design (final)

| Control | Default | Purpose |
|---|---|---|
| Async fetch | `httpx.AsyncClient` + stream | Avoid blocking the ASGI event loop |
| Single-flight lock | `asyncio.Lock` | One in-flight refresh at a time |
| Fresh TTL | 300s | Prefer cached keys while fresh |
| **Max stale grace** | **600s** after last successful fetch | Short outage availability for **known** kids only |
| Refresh backoff | 5s after failed fetch | Prevent thundering-herd sequential 5s fetches |
| Unknown-kid force min interval | 10s | Bound rotation-probe network attempts |
| Unknown-kid negative TTL | 30s | Skip repeats for the same kid |
| Negative-cache max entries | 256 | Bound memory under kid spray |
| Kid charset/length | `[A-Za-z0-9_-]{1,128}` | Reject oversized/invalid kids before cache/network |
| Response bound | 64 KiB / 32 keys | Cap parse cost |

### Security / availability tradeoff

- **Within max stale (≤600s):** if JWKS refresh fails, previously fetched keys may still verify signatures. JWT `exp`/`nbf`/audience/issuer checks still apply. This bridges short Cloudflare JWKS blips without taking the API down.
- **After max stale:** fail closed (`jwks_stale` / `jwks_http`) even for previously known kids until a successful refresh. A revoked key cannot be trusted indefinitely during a prolonged outage.
- Failed refreshes arm backoff so concurrent waiters do **not** each open another slow HTTP call.
- Force-refresh timestamps advance on **failure** as well as success, so unknown-kid spray cannot storm the JWKS endpoint.
- Negative-cache entries are pruned on expiry and capped by size (evict soonest-expiring).

## Dual authentication

1. Cloudflare Access JWT — may reach `/api/**`.
2. FashionRise HS256 Bearer — which Studio user.

Enabling Access JWT validation does **not** enable registration or auto-provision users.

## Pre-enable staging gate (operator)

1. Confirm team domain + Application AUD from Zero Trust dashboard.
2. Confirm Cloudflare injects exactly one `Cf-Access-Jwt-Assertion` and Nginx forwards it unchanged.
3. Confirm private AOP client binding.
4. Exercise protected APIs with a real Access session; registration stays disabled.
5. Rollback: `CF_ACCESS_JWT_VALIDATION=false` + API restart.

## Rollback

Set `CF_ACCESS_JWT_VALIDATION=false` and restart API. No schema / Nginx / Cloudflare changes in this PR.
