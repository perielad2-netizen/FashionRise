# FashionRise — Public Email Registration Activation

**Purpose:** Operator procedure to enable **self-service email registration** with ownership verification after the product PR merges.  
**Does not authorize itself.** Do not change production until Technical PM / operator approval names this procedure.

**Out of scope:** Apple IAP gate flips, Codemagic / App Review, automatic backend deploys from this document alone.

---

## Modes

| `REGISTRATION_MODE` | Behavior |
|---|---|
| unset + `REGISTRATION_ENABLED=false` | **closed** (default) |
| unset + `REGISTRATION_ENABLED=true` | **invite_only** (legacy) |
| `invite_only` | Invitation code required; verified immediately; tokens issued |
| `public` | No invite; verification email required before login |
| `closed` | POST `/auth/register` forbidden |

**Fail closed:**

- `REGISTRATION_MODE=public` without real SMTP (`SMTP_HOST` + `SMTP_FROM_EMAIL`) keeps **effective mode closed**.
- `EMAIL_DELIVERY_BACKEND=capture` satisfies readiness **only** when **both** `TESTING=true` **and** `ENVIRONMENT` is not `production`. Production with `TESTING=true` still keeps effective mode closed and must not capture mail.
- Authenticated SMTP requires encrypted transport (`SMTP_USE_TLS=true` or port `465` SMTPS).

Status payload reports the exact prerequisite when public cannot activate.

---

## Working product journey (target)

1. Visitor opens `/login` and sees **Don't have an account? Create Account**.
2. Completes email / username / password (no invitation code).
3. Sees **Check your email** — no Studio session yet.
4. Opens the one-time link (`/verify-email#token=…` fragment — not a query string).
5. SPA clears the fragment from history and shows **Confirm email** (opening alone does not verify — scanners cannot consume tokens).
6. Confirm → Studio. Logout / login with the same password works.
7. Google Sign-In and existing invited accounts continue unchanged.
8. New public users start with normal Stars; never admin / never unlimited.

---

## Stage status (production)

| Stage | Status | Notes |
|---|---|---|
| **1 — BE foundation** | **DONE 2026-11-11** | Deployed `ba619985…` · Alembic **028** · backup `public-reg-stage1-20261111T190454Z` |
| **2 — Nginx + visitor IP** | **DONE 2026-11-11** | Cloudflare `real_ip` · register/status/verify/resend allowlisted · `TRUST_PROXY_HEADERS=true` · rollback `public-reg-activate-20261111T191438Z` |
| **3 — FE deploy** | **DONE 2026-11-11** | `/var/www/fashionrise/releases/public-reg-activate-c0a942ef` · prior `42a4bce2` preserved |
| **4 — SMTP + public mode** | **BLOCKED** | No `SMTP_*` on VPS. Keep `REGISTRATION_MODE=closed` until owner configures SMTP, then set `public` + restart API |

## Exact safe production activation steps (ordered)

| Step | Change | Notes |
|---|---|---|
| **1. Backup DB** | Snapshot `fashionrise_beta` | **Stage 1 done** — `/var/backups/fashionrise/public-reg-stage1-20261111T190454Z/` |
| **2. Backend deploy** | Deploy approved SHA containing public registration | **Stage 1 done** — `/opt/fashionrise/src` @ `ba619985…` with `REGISTRATION_MODE=closed` |
| **3. Migration `028`** | `alembic upgrade 028` | **Stage 1 done** — head **028**; existing users backfilled `email_verified=true` |
| **4. Configure SMTP** | `EMAIL_DELIVERY_BACKEND=smtp`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM_EMAIL`, credentials | **Stage 2** — **Do not** set `capture`. If `SMTP_USERNAME` is set, require `SMTP_USE_TLS=true` or port `465`. Confirm a test message from the API host. |
| **5. Nginx + visitor IP** | Proxy register / verify-email / resend / registration/status | **Stage 2** — Extend auth regex (today register is edge-denied; status/verify/resend not allowlisted). For per-visitor SlowAPI buckets, apply Option B `real_ip` + overwrite `X-Real-IP` then set `TRUST_PROXY_HEADERS=true` (see `PROPOSED-NGINX-REGISTER-ALLOWLIST.md`). |
| **6. Flip mode** | `REGISTRATION_MODE=public` + restart `fashionrise-api` | **Stage 3** — Confirm `GET /api/v1/auth/registration/status` → `mode=public`, `registration_available=true`, `email_delivery_configured=true`. |
| **7. Frontend** | Deploy SPA from the same product SHA | **Stage 3** — Fragment verify + Confirm button. Login logo unchanged. Vite registration flag may stay false. |
| **8. Accept** | Create → confirm email → login; concurrent verify (one win); resend cooldown; duplicate email/username; invite_only + Google regression | Rate-limit smoke with distinct visitor IPs after Option B. |

### Rollback

1. `REGISTRATION_MODE=closed` (or remove) + restart API.  
2. Optional: restore prior Nginx deny on register.  
3. Leave Alembic at **`028`** (do not downgrade after verifications).  
4. Existing users and balances unchanged.

---

## Security notes (hardened)

| Control | Behavior |
|---|---|
| Token handoff | URL **fragment** only; POST body on confirm; history scrubbed |
| Single-use | Atomic `UPDATE … WHERE used_at IS NULL` — concurrent redeem → one success |
| Lock order | Always **`users` `FOR UPDATE` then** verification-token mint/claim (verify + resend) — avoids verify/resend deadlocks |
| Resend | `users.email_verification_last_sent_at` under `SELECT FOR UPDATE` |
| Commit vs send | User + token commit **before** SMTP; delivery failure → resend recovers |
| Capture backend | Allowed only when `TESTING=true` **and** `ENVIRONMENT≠production` (config + delivery) |
| Rate limit IP | Requires trusted Nginx overwrite + `TRUST_PROXY_HEADERS=true` |

---

## Production prerequisites (exact)

- SMTP delivery: `SMTP_HOST`, `SMTP_FROM_EMAIL` (+ credentials + TLS when authenticated).
- Migration `028` applied.
- Nginx allows POST register + verify-email + resend-verification + GET registration/status.
- For meaningful per-visitor registration rate limits: Cloudflare `real_ip` Option B + `TRUST_PROXY_HEADERS=true`.
- Public IAP purchasing/credit gates remain **OFF** unless separately approved.

---

## Related

- Invite activation (legacy): `docs/deploy/REGISTRATION-ACTIVATION.md`
- Nginx register allowlist: `docs/deploy/PROPOSED-NGINX-REGISTER-ALLOWLIST.md`
- Project status: `docs/00-PROJECT-STATUS.md`
