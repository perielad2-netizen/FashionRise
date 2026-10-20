# FashionRise — WEB-V3B Stage C: Registration activation readiness

**Stage:** C — **READ-ONLY / PREPARATION ONLY**  
**Date (UTC):** 2026-10-20  
**GitHub `main`:** `8c6a391a0d5bb3acc5e697e63c47e3ec242ec9fd`  
**Verdict:** **BLOCKED_PENDING_TRUST_BOUNDARY_VERIFICATION**

**Not authorized in Stage C:** backend deploy, migrations, Nginx/Cloudflare edits, `REGISTRATION_ENABLED=true`, invitations, users, frontend switch, PR merges.

Related: `docs/deploy/WEB-V3B-TRUST-BOUNDARY.md` · `docs/deploy/PROPOSED-NGINX-REGISTER-ALLOWLIST.md` · Stage A/B PWA docs · `docs/WEB-V3B-INVITE-REGISTRATION-QA.md` · draft PR #21 (Stage B; **not yet merged** — reconcile after independent merge).

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
| AOP | **PASS (custom)** | FashionRise-**private** AOP CA (not Cloudflare global) · `ssl_verify_client on` · no-cert **400** — details in trust-boundary doc |
| Cloudflare Access (edge) | **PASS** | no-cookie `/login` **302** to Access — **not** origin JWT validation |
| Origin Access JWT | **DRAFT code / not deployed** | Implementation draft PR [#24](https://github.com/perielad2-netizen/FashionRise/pull/24) (`CF_ACCESS_JWT_VALIDATION` default **false**; API `/api/**` only). **Not merged/deployed** — still blocks Stage D until reviewed, merged, configured (TEAM_DOMAIN+AUD), and enabled under approved deploy |
| `ngx_http_realip_module` | **PASS** | Built-in; dry-config `nginx -t` accepts `set_real_ip_from` / `real_ip_header` |
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

## 4. Decision Gate 0 — Cloudflare → Nginx real client IP (amended)

**Problem:** `$remote_addr` is the Cloudflare edge; trusting visitor IP for SlowAPI requires a proven peer ∈ Cloudflare CIDRs before using `CF-Connecting-IP`.

**AOP finding (corrected):** Origin trusts a **FashionRise-private AOP CA** (`CN = FashionRise Private AOP CA`), not Cloudflare’s **global** shared AOP cert. Custom AOP is zone/hostname-class and stronger than global AOP, but **does not replace** (1) `real_ip` + explicit CF ranges for header provenance, or (2) origin Access JWT validation for Access-application binding. Full evidence: `docs/deploy/WEB-V3B-TRUST-BOUNDARY.md`.

### Options (PM-aligned)

| Option | Mechanism | Recommendation |
|---|---|---|
| **B (preferred)** | FashionRise-only `set_real_ip_from` **official Cloudflare IPv4/IPv6 CIDRs** + `real_ip_header CF-Connecting-IP`; then overwrite `X-Real-IP` / `X-Forwarded-For` with normalized `$remote_addr` on **all** proxied API locations | **Required design for Stage D** |
| **A** | Unconditional `$http_cf_connecting_ip` without peer allowlist | **Rejected** as primary design |
| **C** | `TRUST_PROXY_HEADERS=false` | Shared `127.0.0.1` bucket — **not acceptable** for registration activation |
| **D** | Overwrite with edge `$remote_addr` without real_ip | Shared CF edge buckets — **reject** |

**Also blocking:**

- Origin **Access JWT (AUD) validation** — design in `docs/deploy/WEB-V3B-ORIGIN-ACCESS-JWT-DESIGN.md` (**edge-only residual risk not approved**).
- Operator confirm Cloudflare dashboard AOP client matches FashionRise fingerprint.
- N3/N4 **fail-closed** if `CF-Connecting-IP` missing/malformed (no silent edge buckets) — see trust-boundary doc.
- Merge/deploy SlowAPI hardening draft PR #23 before `TRUST_PROXY_HEADERS=true`.
- Reconcile after PR #21 merges; keep PR #22 blocked until then.

**Stage D must not set `TRUST_PROXY_HEADERS=true` until Option B is applied, negative tests pass, and backend parser hardening is deployed.**
---

## 5. Exact Stage D activation sequence (proposed)

Ordered checkpoints. Each has a rollback. FashionRise only.

### D0 — Preflight & decisions

- Confirm `main` SHA approved for backend (include SlowAPI `ipaddress` hardening).
- Confirm Decision Gate 0 **Option B** + Access JWT plan accepted.
- Confirm Access roster for invitee(s).
- Confirm Stage B frontend still `8c6a391a` (or newer approved gated build).
- Confirm `mkdir -m 700 /var/lib/fashionrise/invites` as `fashionriseapp` (not `/root`).

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

### D4 — Nginx POST-only register allowlist + Option B real_ip

- Scope `set_real_ip_from` / `real_ip_header` to FashionRise HTTPS `server` only (full current CF CIDR lists).
- Overwrite `X-Real-IP` / `X-Forwarded-For` with `$remote_addr` on login, refresh, logout, me, register, designs.
- Apply proposed register location (POST only).
- `nginx -T` isolation check → `nginx -t` → reload.
- Run negative tests N1–N8 from trust-boundary doc; confirm other VPS sites unaffected.
- Probe: register POST reaches API but app still Forbidden while flag false.

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

- As `fashionriseapp` (or root writing into a fashionriseapp-owned path):  
  `python scripts/manage_invitations.py create … --code-file /var/lib/fashionrise/invites/<invitee>.code`  
  (`O_EXCL`, mode `0600`, no symlink, revoke on delivery failure).
- Deliver out-of-band; **never** paste codes into tickets/chats/agent logs.
- Do not create invites before D6. **Do not** use `/root/…`.

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

1. **Option B real_ip + CF CIDRs** — design proposed; **not applied**; negative tests not yet executed on live Nginx.
2. **Origin Access JWT (AUD) validation** — draft PR #24 exists (default off, API-only); **not merged/deployed/enabled**. Required before claiming Access-bound origin.
3. **SlowAPI `ipaddress` hardening** — separate draft code PR; must land before `TRUST_PROXY_HEADERS=true`.
4. **Operator confirm** Cloudflare dashboard uses FashionRise custom AOP client (not global).
5. **Expired Access session** still untested with permanent SW (Stage B residual).
6. **PR #21** (Stage B docs) **merged** at `ef4c42c2` — this PR rebased/reconciled; operator **6/6 PASS** preserved.
7. Invite codes only via `/var/lib/fashionrise/invites/` + `--code-file`.

---

## 9. Overall verdict

| Area | Status |
|---|---|
| Production preflight | **PASS** |
| Backend deploy readiness (reg off) | **READY** (code) |
| Migration `004` | **READY** (smoke PASS) |
| Edge Access + custom AOP (current) | **PASS** (observed) |
| Trust boundary (real_ip Option B + JWT + parser) | **BLOCKED** — unverified |
| Nginx allowlist design | **DRAFTED** — not applied |
| Frontend UI activation design | **READY** (gated build) |
| Stage B operator acceptance | **6/6 PASS** (preserved) |
| Expired Access acceptance | **PENDING** |

### **BLOCKED_PENDING_TRUST_BOUNDARY_VERIFICATION**

Stage D remains **unauthorized**. Reassess only after:

1. Option B Nginx design approved and verification/negative tests planned or completed.
2. Access JWT origin plan accepted (or residual risk explicitly accepted by PM).
3. SlowAPI hardening PR reviewed.
4. PR #21 merged/reconciled without losing Stage B 6/6.
5. Explicit Stage D authorization.