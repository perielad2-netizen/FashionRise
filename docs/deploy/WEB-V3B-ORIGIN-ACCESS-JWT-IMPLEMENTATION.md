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

**Do not claim origin-wide Access JWT enforcement** from this middleware alone. Static and document navigations remain edge Access + AOP until a separate Nginx `auth_request` (or equivalent) is designed, reviewed, and deployed.

## Behavior

- Header-only: `Cf-Access-Jwt-Assertion` (case-insensitive). **No cookie fallback** (avoids header/cookie ambiguity).
- Duplicate or comma-joined assertion header values → **403** (`ambiguous_header`).
- RS256 only; JWKS from `{CF_ACCESS_TEAM_DOMAIN}/cdn-cgi/access/certs`; TTL cache + unknown-`kid` refresh; 5s HTTP timeout.
- Exact issuer = validated team domain; audience must match `CF_ACCESS_AUD`; `exp` required; `nbf` verified when present; ≤60s leeway.
- Failures → generic `403 {"detail":"Access denied"}`. Logs reason **codes only** (never raw JWT, cookies, email, or secrets).
- Does **not** auto-create FashionRise users from Cloudflare identity.
- Default `CF_ACCESS_JWT_VALIDATION=false`. When `true` with missing/invalid `CF_ACCESS_TEAM_DOMAIN` or empty `CF_ACCESS_AUD` → **startup RuntimeError** (fail closed).

## Dual authentication (post Stage D intent)

1. Cloudflare Access JWT — may reach `/api/**`.
2. FashionRise HS256 Bearer — which Studio user (existing deps).

Both remain independent. Enabling this flag does not enable registration.

## Operator prerequisites (dashboard — not done by this PR)

1. Confirm Zero Trust team domain URL (candidate observed: `black-flower-30bb.cloudflareaccess.com`).
2. Copy FashionRise Access **Application Audience (AUD)** tag.
3. Confirm private AOP client cert still bound in Cloudflare (unchanged by this PR).
4. Separate approved deploy to set env + restart API — **not authorized here**.

## Rollback

Set `CF_ACCESS_JWT_VALIDATION=false` and restart API. No schema / Nginx / Cloudflare changes in this PR.
