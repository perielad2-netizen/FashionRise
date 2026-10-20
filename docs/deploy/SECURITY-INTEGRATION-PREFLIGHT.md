# FashionRise — Security Integration Preflight (read-only)

**Date (UTC):** 2026-10-20  
**GitHub `main`:** `4aed16ce9ea22d919266d85b8372e9fc546db078` (PRs #21–#24 merged in GitHub)  
**Assignment:** preparation only — **no production changes authorized**  
**Stage C verdict:** remains **`BLOCKED_PENDING_TRUST_BOUNDARY_VERIFICATION`**

This runbook prepares controlled deployment of merged backend security code (SlowAPI `ipaddress` parser + origin Access JWT middleware) while preserving current production behavior. Registration stays disabled across all checkpoints.

---

## 1. Production preflight results (read-only SSH)

| Check | Result |
|---|---|
| Host | `appserver` · 2026-10-20T20:33Z |
| `fashionrise-api` | **active** · `127.0.0.1:8010` · `/health` → `{"status":"ok"}` |
| Nginx / PostgreSQL | **active** |
| Running backend revision | **`85b6561b338e31c102d101c8d458a1624e7b9f29`** (`/opt/fashionrise/src`) — **does not** contain Access JWT modules yet |
| Frontend Nginx root | `/var/www/fashionrise/releases/8c6a391a` · REVISION `8c6a391a0d5bb3acc5e697e63c47e3ec242ec9fd` |
| `VITE_REGISTRATION_UI_ENABLED` | `false` |
| SW sha256 | `a51964e6acf2f2f7bd0c2c62caa9ecc49a8cdca5e8cfcc2944263a8eae43007e` |
| Alembic (prod DB) | **`003`** · `registration_invitations` **absent** · `users=1` |
| Edge Access (no cookie) | HTTPS `/` and `/login` → **302** to team host `black-flower-30bb.cloudflareaccess.com` (login challenge; response bodies/tokens not retained) |
| AOP (no client cert) | Direct origin HTTPS → **400** |
| AOP CA | `/etc/fashionrise/aop/ca.crt` · `CN=FashionRise Private AOP CA` (private, not global) |
| AOP client cert (on disk) | `CN=FashionRise Cloudflare AOP Client` · issuer private CA · **dashboard binding still operator-PENDING** |
| `REGISTRATION_ENABLED` in `.env` | **ABSENT** (code default false once new code runs) |
| `CF_ACCESS_JWT_VALIDATION` | **ABSENT** |
| `TRUST_PROXY_HEADERS` | **ABSENT** |
| `CF_ACCESS_TEAM_DOMAIN` / `CF_ACCESS_AUD` | **ABSENT** |
| Nginx Option B (`real_ip` / CF CIDRs) | **Not present** |
| Explicit `Cf-Access-Jwt-Assertion` `proxy_set_header` | **Not present** (see §2) |
| `/var/lib/fashionrise/invites/` | **Not created** (parent `750` `fashionriseapp`) |
| Isolation | Other sites enabled: `pickwise`, `curecompass`, `kehilabapark.app` — not modified |
| Disk | ~83G free |
| Backups | Stage B `web-pwa-stageb-20261020T163237Z` · WEB-V3A `web-v3a-deploy-20261020T124335Z` (+ nginx/AOP historical copies) |

**Uvicorn:** `/opt/fashionrise/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --workers 1` as `fashionriseapp` (started 2026-10-20 12:44).

---

## 2. Cloudflare JWT integration readiness

### 2.1 Nginx API proxy behavior (current)

Proxied locations only:

- `~ ^/api/v1/auth/(login|refresh|logout|me)$`
- `~ ^/api/v1/designs(?:/.*)?$`

Each sets: `Host`, `X-Real-IP $remote_addr`, `X-Forwarded-For $proxy_add_x_forwarded_for`, `X-Forwarded-Proto https`.

**Findings:**

1. No `proxy_pass_request_headers off` anywhere → Nginx **default is on**, so inbound client headers (including `Cf-Access-Jwt-Assertion` if Cloudflare injects it) are generally forwarded to Uvicorn **unless** stripped by another layer.
2. Config does **not** explicitly pass or sanitize `Cf-Access-Jwt-Assertion`. For Checkpoint C, prefer an **explicit** single-value forward on both API locations, e.g.  
   `proxy_set_header Cf-Access-Jwt-Assertion $http_cf_access_jwt_assertion;`  
   and confirm duplicates cannot be introduced. Do **not** log header values.
3. Cookie fallback is **not** implemented in FastAPI (by design). Origin validation requires the assertion header.
4. Static HTML / `sw.js` / assets are **not** covered by Access JWT middleware (edge Access + AOP only).

### 2.2 Operator Cloudflare Zero Trust prerequisites (dashboard)

Confirm and record offline (do not paste secrets into chat/git):

| Item | Candidate / status |
|---|---|
| Team domain | Observed login host: `https://black-flower-30bb.cloudflareaccess.com` — **confirm** in Zero Trust |
| FashionRise Application Audience (AUD) | Copy from Zero Trust → Applications → FashionRise → Application Audience — **required before Checkpoint C** |
| FashionRise-specific AOP client | Origin trusts private CA + on-disk client cert `CN=FashionRise Cloudflare AOP Client` — **confirm uploaded/active** for this hostname in Cloudflare |
| Assertion injection | With a valid Access browser session, confirm API XHR/fetch to `/api/v1/...` includes **exactly one** `Cf-Access-Jwt-Assertion` at the origin (operator staging probe; never paste JWT) |

---

## 3. Isolated compatibility tests (`main` @ `4aed16ce`)

Environment: disposable DBs only (`fashionrise_test` / `fashionrise_v3a_qa`). **Never** `fashionrise_beta`.

| Test | Result |
|---|---|
| Defaults: `registration_enabled=false`, `cf_access_jwt_validation=false`, `trust_proxy_headers=false` | **PASS** (settings + create_app) |
| Full backend pytest | **212 passed**, **1 failed** (baseline unrelated) |
| Focused JWT + rate-limit modules | Covered in full suite |
| Schema **003** disposable upgrade + login /me /designs/my + register disabled | **PASS** (`SCHEMA_003_FLAGS_OFF_COMPAT_OK`) — invitations table absent |
| Ruff/mypy on security modules | **clean** |

**Baseline failure (unrelated):** `tests/test_gpt6_luna_live_eval.py::test_cli_default_is_dry_run` — EVAL GUARD expects branch `cursor/openai-gpt6-luna-77c6`.

**Implication for Checkpoint A:** Deploying `main` backend code **without** migration `004` and with all flags off is compatible with production schema `003` for existing login/design flows.

---

## 4. Exact revisions

| Item | SHA / value |
|---|---|
| GitHub `main` (deploy source) | `4aed16ce9ea22d919266d85b8372e9fc546db078` |
| Production backend (live) | `85b6561b338e31c102d101c8d458a1624e7b9f29` |
| Production frontend | `8c6a391a0d5bb3acc5e697e63c47e3ec242ec9fd` |
| Production Alembic | `003` |
| Merged security PRs (GitHub) | #21 docs · #22 Stage C docs · #23 SlowAPI · #24 Access JWT |

---

## 5. Configuration requirements (flags remain OFF for Checkpoint A)

After code deploy, ensure `backend/.env` (or equivalent) contains **explicit** safeties:

```bash
REGISTRATION_ENABLED=false
CF_ACCESS_JWT_VALIDATION=false
TRUST_PROXY_HEADERS=false
# Leave unset/empty until Checkpoint C:
# CF_ACCESS_TEAM_DOMAIN=
# CF_ACCESS_AUD=
```

Do **not** run `alembic upgrade 004` in any checkpoint of this preflight series.

---

## 6. Nginx Option B — isolated validation plan (not installed)

Scope: FashionRise HTTPS `server` only. Re-fetch CIDRs at execution time from:

- https://www.cloudflare.com/ips-v4 (currently 15 lines observed in preflight fetch)
- https://www.cloudflare.com/ips-v6 (currently 7 lines)

### Draft directives (staging file only)

```nginx
# FashionRise HTTPS server — Option B (DO NOT install without Checkpoint D auth)
# set_real_ip_from <each current CF IPv4/IPv6 CIDR>;  # never 0.0.0.0/0
real_ip_header CF-Connecting-IP;
# real_ip_recursive off;  # confirm desired behavior in staging

# On proxied API locations — overwrite, do not append client chains:
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $remote_addr;
proxy_set_header X-Forwarded-Proto https;
# Recommended for Checkpoint C (separate):
# proxy_set_header Cf-Access-Jwt-Assertion $http_cf_access_jwt_assertion;
```

N3/N4 fail-closed for missing/malformed `CF-Connecting-IP` after peer ∈ CF ranges must be staging-proven (map/`if` → 400 on API locations). Silent shared-edge buckets are forbidden.

### Negative tests N1–N9 (from `WEB-V3B-TRUST-BOUNDARY.md`)

| ID | Scenario | Expected |
|---|---|---|
| N1 | Forged client X-Real-IP/XFF from CF peer | Overwritten; visitor key from real_ip |
| N2 | Forged CF-Connecting-IP from non-CF peer | `$remote_addr` unchanged; AOP still required |
| N3 | Missing CF-Connecting-IP from CF peer | **Fail closed** (no silent edge bucket) |
| N4 | Malformed CF-Connecting-IP | Fail closed + FastAPI `ipaddress` reject |
| N5 | IPv4 legitimate client | Correct bucket |
| N6 | IPv6 legitimate client | Correct bucket |
| N7 | Two distinct Access clients | Distinct SlowAPI buckets with `TRUST_PROXY_HEADERS=true` |
| N8 | Neighbor vhosts (PickWise etc.) | Unaffected |
| N9 | Duplicate/ambiguous X-Real-IP to API | FastAPI fail-closed (PR #23) |

**Do not** set `TRUST_PROXY_HEADERS=true` until Option B + N1–N9 pass.

---

## 7. Checkpoint rollout plan (none authorized by this document)

Registration **disabled** in every checkpoint. No invitations/users created.

### Checkpoint A — Deploy merged backend security code, flags OFF

**Goal:** Run `main` backend at origin with identical security posture (JWT off, trust proxy off, registration off).  
**DB:** stay on Alembic **003** (no `004`).  
**Nginx/CF:** unchanged.

**Proposed steps (authorization required before any command):**

1. Backup: copy `/opt/fashionrise/src` revision + `backend/.env` (redacted inventory) + `systemctl cat fashionrise-api` to `/var/backups/fashionrise/security-cp-a-<UTC>/`.
2. `git -C /opt/fashionrise/src fetch origin main && git -C /opt/fashionrise/src checkout 4aed16ce` (or merge/ff to that SHA).
3. Ensure venv deps still satisfy `requirements.txt` (no prod pip without approval if versions drift).
4. Write explicit flag lines in `.env` (§5).
5. `systemctl restart fashionrise-api` → curl `127.0.0.1:8010/health`.
6. Smoke: Access-authenticated browser login + Studio designs (operator); register still 403 at Nginx and app.

**Rollback A:**

```bash
# AFTER authorization only — illustrative
git -C /opt/fashionrise/src checkout 85b6561b338e31c102d101c8d458a1624e7b9f29
# restore .env from backup if modified
systemctl restart fashionrise-api
curl -sS http://127.0.0.1:8010/health
```

### Checkpoint B — Validate real Access JWT forwarding

**Goal:** Prove Cloudflare injects assertion and Nginx delivers exactly one value to Uvicorn (still `CF_ACCESS_JWT_VALIDATION=false`).  
**Method:** operator/staging probe with Access session; inspect presence/count only — **never log token**.  
**Optional Nginx prep (still needs auth):** explicit `proxy_set_header Cf-Access-Jwt-Assertion ...` on API locations only.

### Checkpoint C — Enable API-only Access JWT validation

**Prereqs:** Checkpoint B PASS · team domain + AUD set · rollback drilled · registration still false.  
**Steps (auth required):** set `CF_ACCESS_TEAM_DOMAIN` + `CF_ACCESS_AUD` · `CF_ACCESS_JWT_VALIDATION=true` · restart API · smoke login/designs · missing assertion → 403.  
**Rollback C:** `CF_ACCESS_JWT_VALIDATION=false` + restart.

### Checkpoint D — FashionRise-only Option B + `TRUST_PROXY_HEADERS`

**Prereqs:** Checkpoint A code live · N1–N9 staging PASS · PR #23 parser live.  
**Steps (auth required):** install Option B in FashionRise server only · `nginx -t` · reload · set `TRUST_PROXY_HEADERS=true` · restart API · N7 two-client buckets.  
**Rollback D:** restore prior nginx from backup · `TRUST_PROXY_HEADERS=false` · reload/restart.

---

## 8. Risks and blockers

| Risk / blocker | Severity | Notes |
|---|---|---|
| Origin JWT not yet proven end-to-end | High for C | Header path must be verified before enable |
| AOP dashboard client match PENDING | High for trust | Disk CA/client ≠ confirmed Cloudflare upload |
| Option B not applied | High for D | Do not enable trusted proxy yet |
| Expired Access session test PENDING | Medium | Stage B residual |
| Invites directory missing | Medium | Only needed before invitations (not these checkpoints) |
| Uvicorn default proxy-headers | Medium | Documented; Option B overwrite mitigates |
| Neighbor apps on same VPS | Low if scoped | Keep all nginx edits FashionRise-only |

---

## 9. GO / NO-GO for Checkpoint A

### **GO (conditional)** for Checkpoint A only

Deploying GitHub `main` backend (`4aed16ce`) with **all security/registration flags explicitly false**, **no migration 004**, and **no Nginx/CF changes** is compatible with:

- Production schema `003`
- Existing login / me / designs flows
- Current edge Access + private AOP posture

**Conditions before executing Checkpoint A:**

1. Explicit Technical PM / operator authorization for backend git update + `fashionrise-api` restart only.
2. Pre-restart backup of `/opt/fashionrise/src` SHA + `.env` + unit file.
3. Post-restart smoke: health, Access login, designs; register remains denied.
4. No other checkpoints implied.

### **NO-GO** for Checkpoints B/C/D, Stage D, migration 004, registration, invitations, Nginx/CF changes

until separately authorized after this preflight review.
