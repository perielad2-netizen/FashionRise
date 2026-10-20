# FashionRise — Origin Cloudflare Access JWT validation (design only)

**Status:** architecture approved in principle for a **separate draft implementation PR**. **Not deployed.**  
**Related:** `docs/deploy/WEB-V3B-TRUST-BOUNDARY.md` · Stage C readiness  
**Residual edge-only Access risk:** **not approved** by Technical PM — this layer is required before registration activation.

### Coverage boundary (explicit)

FastAPI middleware protects **application APIs** (`/api/**` after path normalization), **not** Nginx-served static HTML (`/index.html`, `/sw.js`, `/assets/**`, SPA document navigations). Those remain under **edge Cloudflare Access + FashionRise-private AOP** unless a separate Nginx `auth_request` design is approved later. Do **not** claim origin-wide Access JWT enforcement from API middleware alone.

## 1. Goal

Ensure every request that reaches FashionRise **API** handlers under `/api/**` was authorized by **this** Cloudflare Access application, even if:

- Custom AOP mTLS is satisfied, and/or
- An attacker somehow presents FashionRise’s AOP client certificate.

Edge Access 302 for anonymous browsers remains necessary but is **not** sufficient as the sole Access control.

## 2. Token source & crypto

| Item | Specification |
|---|---|
| Header (preferred) | `Cf-Access-Jwt-Assertion` (also accept `CF-Access-Jwt-Assertion` case-insensitively) |
| Cookie | **Not used** in the first implementation (avoids header/cookie ambiguity). Header-only. |
| Algorithm | `RS256` via existing **`python-jose[cryptography]`** (pinned in `backend/requirements.txt`) |
| JWKS URL | `https://<TEAM_DOMAIN>/cdn-cgi/access/certs` where `<TEAM_DOMAIN>` is `https://<team>.cloudflareaccess.com` |
| Key selection | Match JWT `kid` to JWKS `keys[]` / `public_certs[]`; **do not** hard-code a single PEM; **do not** use only `public_cert` (rotation race) |
| Rotation | CF rotates ~every 6 weeks; previous key valid ~7 days — fetch JWKS on demand with short TTL cache (e.g. 5–15 min) + refresh on unknown `kid` |
| Issuer (`iss`) | Exact team domain URL, e.g. `https://black-flower-30bb.cloudflareaccess.com` (confirm in dashboard; do not invent) |
| Audience (`aud`) | FashionRise Access **Application Audience (AUD) Tag** — stable until app recreate |
| Expiry | Enforce `exp` (and `nbf` if present) with small clock skew ≤ 60s |

**Secrets:** Team domain + AUD are configuration, not signing secrets. Store in production env (`CF_ACCESS_TEAM_DOMAIN`, `CF_ACCESS_AUD`). **Never** commit AUD/tokens/JWTs to the repo or logs.

Observed edge login host from Stage A/B probes: `black-flower-30bb.cloudflareaccess.com` — treat as **candidate** until operator confirms team domain + AUD from Zero Trust → Applications → FashionRise → Application Audience.

## 3. Validation algorithm (fail closed)

1. If `CF_ACCESS_AUD` or `CF_ACCESS_TEAM_DOMAIN` unset while feature enabled → **fail closed** (503/403), do not bypass.
2. Read assertion header; if missing, optionally cookie; if still missing → **403**.
3. Fetch/cache JWKS from `{TEAM_DOMAIN}/cdn-cgi/access/certs` over HTTPS; TLS verify on.
4. `jwt.decode` / verify signature with matching `kid`, algorithms=`RS256` only.
5. Require `iss == TEAM_DOMAIN`, `aud` contains/equals `CF_ACCESS_AUD`, `exp` valid.
6. On any failure → **403** with generic body (`Access denied`). Log reason code only (e.g. `missing`, `bad_sig`, `bad_aud`, `expired`) — **never** log raw JWT, email, or full claims in production INFO logs.
7. On success → attach minimal context to request state (e.g. `access_email` from `email` claim if present) for optional audit; do **not** replace FashionRise app JWT auth.

## 4. Compatibility with application JWT auth

| Layer | Role |
|---|---|
| Cloudflare Access JWT | Proves **who may reach the origin app** (outer identity / policy) |
| FashionRise HS256 access/refresh tokens | Proves **which Studio user** is signed in (inner identity) |

Both required for authenticated API use after Stage D:

- Missing Access JWT → never reach login/register/design handlers (403).
- Valid Access JWT + missing/invalid app Bearer → existing 401 Unauthorized from FastAPI auth deps.
- Do **not** auto-provision FashionRise users from Access email in this design (invite-only remains authoritative).

## 5. Where to enforce

### Recommended: FastAPI middleware (primary)

Apply ASGI middleware early (after TrustedHost/CORS as appropriate), **before** route handlers.

| Path class | Access JWT required? |
|---|---|
| `GET /health` (and any future liveness on `:8010`) | **No** — loopback/`127.0.0.1` only is already implied by bind; optionally allow only when `request.client.host` is loopback **and** no forwarded client (see Uvicorn note) |
| Static SPA assets served by **Nginx** (`/assets/*`, `/sw.js`, `/index.html`, …) | Prefer enforce at **Nginx** auth_request **or** accept that SPA HTML is still behind edge Access; origin JWT check on HTML is stronger — see Nginx option below |
| `/api/v1/auth/login\|refresh\|logout\|me` | **Yes** |
| `/api/v1/auth/register` (when allowlisted) | **Yes** |
| `/api/v1/designs/**` | **Yes** |
| Denied API paths (AI/uploads/docs) | Unreachable via Nginx; if ever reached → **Yes** fail closed |
| Future `/docs` etc. | Remain Nginx-denied |

### Optional defense: Nginx `auth_request` subrequest

Nginx calls an internal FastAPI route `GET /internal/access-check` that only validates Access JWT and returns 204/401. Keeps JWT off static file workers if desired. Still keep FastAPI middleware so a mis-proxied API cannot skip the check.

**Do not** disable AOP when adding JWT validation.

## 6. Health checks & internal ops

| Caller | Behavior |
|---|---|
| systemd / local `curl 127.0.0.1:8010/health` | Exempt `/health` only |
| Operator SSH diagnostics | Use loopback health; do not puncture Access JWT for `/api` |
| Migration / CLI (`manage_invitations`) | Process-local DB; no HTTP; unaffected |
| Uvicorn reload workers | N/A |

**Uvicorn interaction:** Production uses `uvicorn … --host 127.0.0.1` with default `--proxy-headers` and trusted host `127.0.0.1`. Nginx-supplied `X-Forwarded-For` may rewrite `Request.client.host`. Health exemption must key off **direct** connection to loopback (e.g. raw ASGI scope before proxy middleware, or require absence of `X-Forwarded-For` / enforce health only on a separate internal bind). Document exact exemption mechanism in the implementation PR.

## 7. Feature flag & rollback

| Env | Meaning |
|---|---|
| `CF_ACCESS_JWT_VALIDATION=false` (default until authorized) | Middleware no-op (current behavior) |
| `CF_ACCESS_JWT_VALIDATION=true` | Fail-closed validation enabled |
| `CF_ACCESS_TEAM_DOMAIN` | Required when enabled |
| `CF_ACCESS_AUD` | Required when enabled |

**Rollback without exposing the app:**

1. Set `CF_ACCESS_JWT_VALIDATION=false` and restart **only** `fashionrise-api` → restores edge-only Access (known residual risk — temporary).
2. Prefer keep flag **true** and fix JWKS/AUD misconfig rather than disabling under attack.
3. Nginx register deny + `REGISTRATION_ENABLED=false` remain independent shutdowns.
4. AOP stays on throughout.

Never “open” origin by disabling AOP to debug JWT.

## 8. Test plan (implementation PR — later)

### Unit

- Valid token (mocked JWKS) → allow.
- Missing header/cookie → 403.
- Bad signature / wrong `kid` → 403.
- Wrong `aud` / wrong `iss` → 403.
- Expired `exp` → 403.
- Alg `none` / HS256 token → 403.
- JWKS fetch failure while enabled → 403 (fail closed; optional stale cache within TTL).

### Integration (disposable / staging)

- Browser Access session → header present → API login works with app JWT.
- Request with FashionRise AOP client cert but **no** Access JWT → 403 on `/api/v1/auth/me`.
- Forged JWT → 403.
- `/health` from loopback without JWT → 200.

### Logging

- Assert raw JWT / `CF_Authorization` never appear in caplog at INFO+.

## 9. Implementation sketch (not committed code)

- Dependency: `PyJWT[crypto]` already available via jose stack — prefer `jwt` + `cryptography` or existing `python-jose` with explicit RS256 + JWKS.
- Module: `app/core/cloudflare_access.py` + middleware registered in `app/main.py`.
- Config fields on `Settings` with defaults **disabled**.
- Separate draft code PR after this design is approved; no secrets in fixtures (use generated RSA keys for unit tests).

## 10. Operator prerequisites before coding merge

1. Confirm team domain string.
2. Copy Application Audience (AUD) Tag from Cloudflare Zero Trust UI.
3. Confirm FashionRise custom AOP client still active (dashboard).
4. Schedule JWKS egress allow from VPS to `*.cloudflareaccess.com` if egress is restricted.

## 11. Out of scope

- Replacing FashionRise user passwords with Access SSO login.
- Storing Access JWTs in the database.
- Changing Cloudflare Access policies in this design phase.
