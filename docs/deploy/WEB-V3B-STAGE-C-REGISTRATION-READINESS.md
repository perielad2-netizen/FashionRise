# FashionRise — WEB-V3B Stage C: Registration activation readiness

**Stage:** C — **READ-ONLY / PREPARATION ONLY**  
**Date (UTC):** 2026-10-20  
**GitHub `main`:** `8c6a391a0d5bb3acc5e697e63c47e3ec242ec9fd`  
**Verdict:** **READY_FOR_STAGE_D_APPROVAL** (with mandatory Decision Gate 0 on client-IP)

**Not authorized in Stage C:** backend deploy, migrations, Nginx/Cloudflare edits, `REGISTRATION_ENABLED=true`, invitations, users, frontend switch, PR merges.

Related: Stage A/B PWA docs · `docs/WEB-V3B-INVITE-REGISTRATION-QA.md` · `docs/deploy/PROPOSED-NGINX-REGISTER-ALLOWLIST.md` · draft PR #21 (Stage B deploy record).

---

## 1. Production preflight (read-only) — PASS

| Check | Result | Evidence |
|---|---|---|
| Frontend root | **PASS** | `/var/www/fashionrise/releases/8c6a391a` · REVISION `8c6a391a…` |
| Backend git HEAD | **PASS** | `/opt/fashionrise/src` = `85b6561b…` · clean |
| `fashionrise-api` | **PASS** | `active` · `127.0.0.1:8010` · `/health` ok |
| Alembic | **PASS** | **`003 (head)`** on `fashionrise_beta` |
| `registration_invitations` table | **PASS (absent)** | `to_regclass` → `None` |
| `REGISTRATION_ENABLED` | **PASS (off)** | unset → defaults false |
| `TRUST_PROXY_HEADERS` | **PASS (off)** | unset → defaults false |
| Nginx register deny | **PASS** | `location = /api/v1/auth/register { return 403; }` (+ suffix deny) |
| AOP | **PASS** | `ssl_verify_client on` · no-cert **400** |
| Cloudflare Access | **PASS** | no-cookie `/login` **302** to Access |
| Users | **PASS** | `users=1` · no production invites |
| Disk / backups | **PASS** | ~83G free · Stage B + WEB-V3A backups present |
| Isolation | **PASS** | Other nginx sites / DBs present; **not touched** |

### Client-IP observation (critical)

Nginx access log `$remote_addr` for live traffic is **Cloudflare edge** (e.g. `172.70.153.166`), not a unique end-user IP. Current proxy blocks set:

```nginx
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
```

Uvicorn access lines show the same `172.70.*` peer after proxy. **Do not assume `$remote_addr` is the visitor.** See Decision Gate 0.

---

## 2. Backend deployment readiness — READY (with registration left off)

### Delta: production `85b6561b` → `main` `8c6a391a` (backend only)

| Area | Change | Risk if deployed with `REGISTRATION_ENABLED=false` |
|---|---|---|
| Migration `004` | New `registration_invitations` table | Additive; apply only after backup |
| `register_user` | Gate + invite lock + `is_admin=False` + IntegrityError→409 | Register still Forbidden until flag true |
| Login / tokens / refresh | Email normalize via invitation helper (strip/lower) | Compatible |
| Designs / ownership | No schema change to designs | Compatible |
| Rate limit | New `TRUST_PROXY_HEADERS` / `X-Real-IP` keying | Default **false** → keys on ASGI peer (`127.0.0.1` behind Nginx) — same shared-bucket posture as today unless Decision Gate 0 completed |
| Scripts | `manage_invitations.py`, bound `run_migration_smoke.py` | Ops only |
| Tests / guards | Fail-closed test DB | No prod effect |

**Existing frontend `8c6a391a` remains compatible** while registration UI stays off (`VITE_REGISTRATION_UI_ENABLED=false`). Create Account stays hidden; `/register` redirects to `/login`.

### Environment variables for Stage D backend

| Variable | Required value until activation window | Notes |
|---|---|---|
| `REGISTRATION_ENABLED` | **`false`** (explicit) | Authoritative signup gate |
| `TRUST_PROXY_HEADERS` | **`false`** until Decision Gate 0 done | Then `true` only with approved Nginx IP overwrite |
| Existing secrets / `DATABASE_URL` / CORS / JWT | unchanged | Do not rotate casually mid-activation |
| `TESTING` | **`false`** | |

Backend must boot and serve login + designs with registration disabled — verified by code defaults and prior WEB-V3B suite.

---

## 3. Migration `004` readiness — PASS (disposable DB only)

Runner: `backend/scripts/run_migration_smoke.py` (fail-closed; never production).

| Smoke | Result |
|---|---|
| `0 → head` on `fashionrise_mig_v3b` | **PASS** → `004` |
| `004 → 003 → 004` | **PASS** |
| Seeded user survives `003 → 004` | **PASS** (`preserve@example.com` retained; invites table created) |
| Reject `fashionrise_beta` as smoke target | **PASS** exit 2 |
| Reject missing `DATABASE_URL_TEST` | **PASS** exit 2 |
| Invite / concurrency / code-file / rate-limit IP / guards | **42 passed** (`test_invite_registration`, `test_rate_limit_ip`, `test_manage_invitations_code_file`, `test_migration_smoke_runner`, `test_test_db_guard`) |

**Production migration procedure (Stage D only — NOT executed):**

1. Fresh `pg_dump` of `fashionrise_beta` to `/var/backups/fashionrise/…`.
2. Deploy backend code at `8c6a391a` (or later approved SHA) with **`REGISTRATION_ENABLED=false`**.
3. As `fashionriseapp`, from `/opt/fashionrise/src/backend`: `alembic upgrade 004` using production `.env` (normal Alembic path — **not** the smoke runner).
4. Verify `alembic current` → `004` and `\dt registration_invitations`.
5. Confirm login still works for the existing user before any Nginx allowlist.

**Downgrade constraint:** `004 → 003` drops `registration_invitations`. Safe only before production redemptions, or after accepting invite-ledger loss. Prefer leave `004` in place and shut registration off via flag + Nginx deny.

---

## 4. Decision Gate 0 — Cloudflare → Nginx real client IP

**Problem:** Proposed allowlist doc previously set `X-Real-IP` / `X-Forwarded-For` to `$remote_addr`. Behind Cloudflare + AOP, `$remote_addr` is the **Cloudflare edge IP**, so SlowAPI buckets would merge many visitors (or entire POPs).

**AOP fact:** `ssl_verify_client on` already proves the TLS peer holds Cloudflare’s Authenticated Origin Pull certificate. Trusting Cloudflare-injected `CF-Connecting-IP` is therefore reasonable **only** on that FashionRise server block.

### Options for PM

| Option | Mechanism | Rate-limit key | Recommendation |
|---|---|---|---|
| **A (preferred)** | `proxy_set_header X-Real-IP $http_cf_connecting_ip;` (and same for XFF overwrite) on **all** proxied API locations; keep AOP; set `TRUST_PROXY_HEADERS=true` | Visitor IP from CF | Prefer for activation |
| **B** | `real_ip_header CF-Connecting-IP` + `set_real_ip_from` Cloudflare IP ranges; then `$remote_addr` becomes visitor | Visitor IP | Acceptable if IP list maintained |
| **C** | Leave `TRUST_PROXY_HEADERS=false` | Shared `127.0.0.1` bucket | **Not acceptable** for registration activation |
| **D** | Overwrite with `$remote_addr` only | Shared CF edge IP | **Reject** for activation |

Updated proposal text lives in `docs/deploy/PROPOSED-NGINX-REGISTER-ALLOWLIST.md`.

**Stage D must not set `TRUST_PROXY_HEADERS=true` until Option A or B is approved and applied to login, refresh, logout, me, register, and designs.**

---

## 5. Exact Stage D activation sequence (proposed)

Ordered checkpoints. Each has a rollback. FashionRise only.

### D0 — Preflight & decisions

- Confirm `main` SHA approved for backend.
- Confirm Decision Gate 0 (Option A or B).
- Confirm Access roster for invitee(s).
- Confirm Stage B frontend still `8c6a391a` (or newer approved gated build).

### D1 — Backup

- `pg_dump` `fashionrise_beta`.
- Copy `/etc/nginx/sites-available/fashionrise.app`.
- Record backend HEAD, Alembic `003`, env flag names (not secret values).

### D2 — Backend deploy (registration still disabled)

- Update `/opt/fashionrise/src` to approved SHA (FashionRise only).
- Ensure `.env`: `REGISTRATION_ENABLED=false`, `TRUST_PROXY_HEADERS=false` (until D5).
- Restart **only** `fashionrise-api`.
- Health + existing-user login + My Designs smoke.

**Rollback:** restore previous backend tree / unit; restart API.

### D3 — Migration `004`

- `alembic upgrade 004`.
- Verify table + `alembic current`.
- Re-check existing login / designs.

**Rollback:** prefer keep `004` + flag off; `downgrade 003` only if PM accepts invite-table drop and no redemptions occurred.

### D4 — Nginx POST-only register allowlist + IP headers

- Apply proposed register location (POST only).
- Apply Decision Gate 0 header strategy on **all** proxied API locations.
- `nginx -t` && reload.
- Probe: register POST reaches API but returns **403/Forbidden** while flag false; GET register still denied; other `/api/` still denied.
- Confirm AOP + Access unchanged.

**Rollback:** restore prior nginx file; reload.

### D5 — Trusted proxy flag

- Set `TRUST_PROXY_HEADERS=true`; restart **only** `fashionrise-api`.
- Spot-check distinct client buckets if feasible (two networks).

**Rollback:** set `false`; restart API.

### D6 — Enable registration (app)

- Set `REGISTRATION_ENABLED=true`; restart **only** `fashionrise-api`.
- Confirm unauthenticated/uninvited register still fails closed.

**Rollback:** set `false`; restart API (immediate).

### D7 — Secure invitation

- `python scripts/manage_invitations.py create … --code-file /root/…` (mode 0600, O_EXCL).
- Deliver out-of-band; **never** paste code into tickets/chats.
- Do not create invites before D6.

**Rollback:** `revoke --id`.

### D8 — Frontend registration UI (immutable build)

- Build with `VITE_API_BASE_URL=/api/v1` and `VITE_REGISTRATION_UI_ENABLED=true`.
- New release dir under `/var/www/fashionrise/releases/<sha>/`.
- Switch Nginx root only after D6–D7 ready (form must not appear before server gates work).
- Keep SW Access-safe assert in build.

**Rollback:** point root back to `8c6a391a` (UI gate off).

### D9 — Controlled second user

- Invitee completes `/register` behind Access.
- Verify `is_admin=false`, invite redeemed once.
- Cross-account privacy suite (section 6).

### D10 — Registration shutdown (if needed anytime)

1. `REGISTRATION_ENABLED=false` + restart API.
2. Nginx restore register `return 403`.
3. Optional: frontend back to UI-gated release.
4. Revoke outstanding invites.
5. Leave migration `004` unless PM orders downgrade.

---

## 6. Security & privacy acceptance plan

### Registration security

| Test | Expected |
|---|---|
| No invite / wrong code / wrong email | Reject |
| Expired / revoked invite | Reject |
| Second redeem of same code | Reject |
| Concurrent redeem | One winner; loser clean failure |
| Register creates `is_admin=false` only | Pass |
| `REGISTRATION_ENABLED=false` | Forbidden even if Nginx allows |
| Nginx GET/extra path register | Denied |
| Uninvited Access member | Cannot register without invite |

### Privacy (two accounts)

| Test | Expected |
|---|---|
| User A cannot GET/PUT/DELETE User B designs | 404/403 as designed |
| My Designs lists only owner rows | Pass |
| Account switch clears prior identity before new session | Pass |
| Studio remounts on user id; IndexedDB keys isolated | No prior artwork visible |
| Existing user still signs in after activation | Pass |

### Cloudflare Access

| Test | Expected |
|---|---|
| No Access session document nav | Access challenge (**302**/login) |
| Valid Access + app login | Works |
| **Genuinely expired Access session** | Access challenge via **network** document (not SW HTML shell) — **still PENDING from Stage B**; required before claiming full Access posture after D8 |

Do **not** create production users/invites during Stage C.

---

## 7. Rollback summary

| Checkpoint | Immediate action |
|---|---|
| After backend deploy | Restore prior `/opt/fashionrise/src` + restart API |
| After `004` | Prefer flag/Nginx off; downgrade only with PM OK |
| After Nginx | Restore site file + reload |
| After flag true | `REGISTRATION_ENABLED=false` |
| After frontend UI on | Root → `8c6a391a` |
| Security incident | Flag off + Nginx 403 + revoke invites + preserve logs |

Never clear IndexedDB to “fix” registration issues. Never touch PickWise / CureCompass / synagogue / other DBs.

---

## 8. Outstanding decisions & risks

1. **Decision Gate 0 (blocking for D4/D5):** approve CF-Connecting-IP (or real_ip) strategy.
2. **Expired Access session** still untested with permanent SW.
3. **Backend deploy window** with registration off still restarts API — schedule for low traffic; confirm no long-running jobs (AI worker already off in prod intent).
4. **Invite delivery** is out-of-band only; operator must use `--code-file`.
5. Reconcile docs: draft PR #21 (Stage B) vs this Stage C PR for `00-PROJECT-STATUS.md`.

---

## 9. Overall verdict

| Area | Status |
|---|---|
| Production preflight | **PASS** |
| Backend deploy readiness (reg off) | **READY** |
| Migration `004` | **READY** (smoke PASS) |
| Security config (Nginx deny, flags off, Access, AOP) | **PASS (current)** |
| Nginx allowlist + TRUST_PROXY design | **READY pending Decision Gate 0** |
| Frontend UI activation design | **READY** (gated build) |
| Expired Access acceptance | **PENDING** (tracked) |

### **READY_FOR_STAGE_D_APPROVAL**

Stage D remains **unauthorized** until Technical PM:

1. Approves Decision Gate 0 (client IP).
2. Explicitly authorizes Stage D execution.
3. Separately accepts residual Access expired-session testing plan.
