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

## 5. Effective safety flags (systemd runtime — not `.env` absence alone)

Checkpoint A requires the **resolved** FastAPI settings under the live `fashionrise-api` process to be false for all three gates. Absence of a key in `backend/.env` is **not** sufficient proof if systemd injects overrides.

### 5.1 Inspect actual runtime configuration (read-only; never print secrets)

```bash
# Unit + drop-ins (paths/names only; redact any Environment= values that look like secrets)
systemctl cat fashionrise-api
systemctl show fashionrise-api -p Environment -p EnvironmentFiles -p WorkingDirectory -p ExecStart -p User --no-pager

# Confirm WorkingDirectory / ExecStart point at FashionRise backend (do not modify under A)
# Expected (preflight): WorkingDirectory=/opt/fashionrise/src/backend
#   ExecStart=/opt/fashionrise/.venv/bin/python -B -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --workers 1
```

### 5.2 Assert effective boolean flags (safe probe — no secrets)

Prefer evaluating settings **as the service user** with the same cwd/venv the unit uses. Print **only** the three booleans:

```bash
sudo -u fashionriseapp -H bash -lc '
  cd /opt/fashionrise/src/backend &&
  /opt/fashionrise/.venv/bin/python - <<'"'"'PY'"'"'
from app.core.config import get_settings
get_settings.cache_clear()
s = get_settings()
print("registration_enabled=", s.registration_enabled)
print("cf_access_jwt_validation=", s.cf_access_jwt_validation)
print("trust_proxy_headers=", s.trust_proxy_headers)
raise SystemExit(0 if (
    s.registration_enabled is False
    and s.cf_access_jwt_validation is False
    and s.trust_proxy_headers is False
) else 2)
PY'
```

**Required result before and after Checkpoint A restart:** all three print `False` and exit code `0`.

Do **not** dump `SECRET_KEY`, `DATABASE_URL`, `CF_ACCESS_AUD`, tokens, or full `.env`.

### 5.3 Production `.env` edits — separate authorization

Writing `REGISTRATION_ENABLED=false` (or any `.env` change) is a **production configuration change**. It is **not** implied by authorization that only covers `git checkout` + `systemctl restart`.

**Preference for Checkpoint A:** if the effective-flag probe (§5.2) already returns all-false on the target code SHA, **leave `.env` untouched**.

If an `.env` edit is later deemed necessary, request that **exact scope** and a secrets-safe rollback copy in the deployment authorization. Never paste `.env` contents into chat/PR/logs.

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
**Docs merge of PR #25 and production Checkpoint A deployment are distinct decisions** — each needs its own operator/PM authorization.

### Checkpoint A — Deploy pinned backend security code, flags OFF (final runbook)

**Pinned backend target SHA (immutable for A):**  
`4aed16ce9ea22d919266d85b8372e9fc546db078`

Do **not** deploy “whatever `origin/main` is at execution time” if it has moved past this SHA. Later docs-only merges must not change the Checkpoint A pin without a new authorization.

**Rollback SHA (current live):** `85b6561b338e31c102d101c8d458a1624e7b9f29`  
**DB:** stay on Alembic **003** (no `004`).  
**Nginx / Cloudflare / frontend release root:** **unchanged**.  
**Scope:** FashionRise backend git checkout + `fashionrise-api` restart only (plus `.env` **only** if separately authorized per §5.3).

#### A0 — Preconditions (hard STOP if any fail)

1. Separate written authorization naming: pin SHA `4aed16ce…`, restart unit `fashionrise-api`, **no** Nginx/CF, **no** migration, **no** flag enablement.
2. Confirm frontend Nginx `root` still `/var/www/fashionrise/releases/8c6a391a` (do not switch).
3. Neighbor sites (`pickwise`, `curecompass`, `kehilabapark.app`) not in scope.

#### A1 — Production Git worktree verification (STOP on surprises)

```bash
cd /opt/fashionrise/src
git rev-parse HEAD                    # expect 85b6561b… before A
git status --porcelain                # must be empty of unexpected tracked diffs
git remote -v                         # FashionRise origin only
ls -ld /opt/fashionrise/src           # owner/mode inventory
```

**Rules:**

- **STOP** if porcelain shows unexpected modified tracked files, divergent branch state, or unknown remotes.
- List untracked files; **preserve** them. **Never** `git clean`, `git reset --hard`, or force-push.
- Confirm ancestry: `git merge-base --is-ancestor 85b6561b338e31c102d101c8d458a1624e7b9f29 4aed16ce9ea22d919266d85b8372e9fc546db078` (or document the intended checkout path).
- Confirm `systemctl show fashionrise-api -p WorkingDirectory -p ExecStart` still points at `/opt/fashionrise/src/backend` and the existing venv uvicorn command — **do not modify the unit under A**.

#### A2 — Secrets-safe backup + rollback package (verify before mutate)

```bash
UTC=$(date -u +%Y%m%dT%H%M%SZ)
B=/var/backups/fashionrise/security-cp-a-$UTC
mkdir -m 700 "$B"
# Code SHA pointer + unit (no secrets)
git -C /opt/fashionrise/src rev-parse HEAD > "$B/PRE_SHA.txt"
systemctl cat fashionrise-api > "$B/fashionrise-api.service.txt"
# .env copy — mode 600, root-only; NEVER cat/less into chat/PR/logs
install -m 600 /opt/fashionrise/src/backend/.env "$B/backend.env"
# Optional: tar of src excluding .git/objects bulk if operator prefers full tree
printf '%s\n' "pre_sha=$(cat "$B/PRE_SHA.txt")" "target_sha=4aed16ce9ea22d919266d85b8372e9fc546db078" "frontend_root_untouched=8c6a391a" > "$B/META.txt"
chmod 600 "$B"/* 2>/dev/null || true
chmod 700 "$B"
ls -la "$B"   # names/modes only — do not display .env contents
```

**Rollback script** (write to `$B/ROLLBACK.sh`, mode `750`, review before use):

```bash
#!/bin/bash
# Checkpoint A rollback — FashionRise backend only. AFTER authorization if auto-invoked.
set -euo pipefail
git -C /opt/fashionrise/src checkout 85b6561b338e31c102d101c8d458a1624e7b9f29
# Restore .env ONLY if it was modified under a separately authorized edit:
#   install -m 600 "$B/backend.env" /opt/fashionrise/src/backend/.env
systemctl restart fashionrise-api
curl -sS -m 5 http://127.0.0.1:8010/health
# Re-run effective flag probe (§5.2) and alembic current == 003
```

Verify: parent `700`, env copy `600`, rollback executable by intended operator (root), script touches **only** `/opt/fashionrise/src` + `fashionrise-api` (no DB migrate, no other vhosts).

#### A3 — Effective flags before mutate

Run §5.2 against **current** `85b6561b` tree (sanity) and record pass/fail.  
After checkout to pin (A4), run §5.2 again **before** restart if import path allows; **required** after restart.

#### A4 — Checkout pinned SHA (no clean/hard reset)

```bash
cd /opt/fashionrise/src
git fetch origin
git checkout 4aed16ce9ea22d919266d85b8372e9fc546db078
test "$(git rev-parse HEAD)" = "4aed16ce9ea22d919266d85b8372e9fc546db078"
# STOP if test fails
# Do not modify Nginx root; do not touch other apps
# requirements.txt is byte-identical to 85b6561b — no pip unless separately authorized
```

#### A5 — Restart API only

```bash
systemctl restart fashionrise-api
systemctl is-active fashionrise-api   # must be active
```

#### A6 — Post-restart acceptance (all required)

| # | Check | Pass criteria |
|---|---|---|
| 1 | API health | `curl -sS http://127.0.0.1:8010/health` → `{"status":"ok"}` |
| 2 | Effective flags | §5.2 all `False` |
| 3 | Alembic | `alembic current` (service venv) → **`003`**; no `registration_invitations` |
| 4 | App JWT login | Existing Access-authenticated operator: login succeeds; `/api/v1/auth/me` OK |
| 5 | Designs | My Designs list + reopen a saved design OK |
| 6 | Registration blocked | `POST /api/v1/auth/register` via public edge still **Nginx 403**; Create Account UI remains hidden |
| 7 | Edge Access | Anonymous HTTPS `/` or `/login` still **302** to Access (no token capture) |
| 8 | AOP | Origin without FashionRise client cert still **400** |
| 9 | Frontend pin | Nginx root still `…/releases/8c6a391a` |
| 10 | Isolation | Other vhosts unchanged |

**Do not** clear browser site data / IndexedDB to “fix” issues.

#### A7 — Automatic STOP / rollback conditions

**Immediate STOP and execute `$B/ROLLBACK.sh` (or equivalent) if any of:**

- `fashionrise-api` fails to become `active`, crash-loops, or `/health` fails
- Effective flags ≠ all false
- Alembic ≠ `003` or unexpected schema objects appear
- Existing user cannot login / `/auth/me` / My Designs / reopen regresses
- Public register is no longer Nginx-denied, or registration UI appears
- Edge Access challenge or AOP denial regresses
- Nginx frontend root or non-FashionRise sites changed
- Any unauthorized `.env` / unit / Cloudflare change detected

After rollback: re-verify health, flags, Alembic `003`, login/designs, Access/AOP.

#### Out of Checkpoint A authorization (explicit)

- Checkpoints **B / C / D**
- Stage D / registration enable / invitations / users
- Migration **004**
- `CF_ACCESS_JWT_VALIDATION=true` / `TRUST_PROXY_HEADERS=true`
- Nginx Option B or any Cloudflare dashboard change
- Assuming JWT assertion forwarding from Nginx defaults (belongs to **B**)

---

### Checkpoint B — Validate real Access JWT forwarding (NO-GO here)

**Goal:** Prove Cloudflare injects assertion and Nginx delivers exactly one value to Uvicorn (still `CF_ACCESS_JWT_VALIDATION=false`).  
Nginx defaults ≠ proof of injection. Operator/staging probe only; **never log tokens**.

### Checkpoint C — Enable API-only Access JWT validation (NO-GO here)

Requires B PASS + team domain + AUD + separate authorization.

### Checkpoint D — FashionRise-only Option B + `TRUST_PROXY_HEADERS` (NO-GO here)

Requires A code live + N1–N9 PASS + separate authorization.

---

## 8. Risks and blockers

| Risk / blocker | Severity | Notes |
|---|---|---|
| Origin JWT not end-to-end verified | High for C | Nginx default header pass ≠ Cloudflare injection proof (Checkpoint B) |
| AOP dashboard client match PENDING | High for trust | Disk CA/client ≠ confirmed Cloudflare upload |
| Option B not applied | High for D | Do not enable trusted proxy; Uvicorn XFF risk remains until D |
| Expired Access session test PENDING | Medium | Stage B residual |
| Invites directory missing | Medium | Only needed before invitations (not Checkpoint A) |
| Neighbor apps on same VPS | Low if scoped | Keep all mutations FashionRise-backend-only |

---

## 9. GO / NO-GO for Checkpoint A

### **CHECKPOINT A PLAN: CONDITIONALLY ACCEPTED** (runbook complete)

Compatible path: pin backend to **`4aed16ce9ea22d919266d85b8372e9fc546db078`**, keep Alembic **003**, keep all three safety flags **effectively false**, no Nginx/CF changes.

**Still required before any production mutation:**

1. Separate operator/PM authorization for **docs merge** (this PR) — optional/independent.
2. Separate operator/PM authorization for **Checkpoint A deployment** naming the pin SHA + restart-only scope.
3. Backup package verified (`700`/`600`, rollback script reviewed).
4. Git worktree clean of unexpected changes; untracked files preserved (no `clean`/`reset --hard`).
5. Post-restart acceptance table (§A6) with automatic rollback triggers (§A7).

### **NO-GO** (unchanged)

Checkpoints B/C/D, Stage D, migration 004, registration, invitations, Nginx/Cloudflare changes, JWT enablement, `TRUST_PROXY_HEADERS=true`.
