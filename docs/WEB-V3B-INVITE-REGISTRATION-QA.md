# WEB-V3B — Invite-Only Beta Registration

**Branch:** `cursor/web-v3b-invite-registration-77c6`  
**Status:** final safety corrections complete — awaiting Technical PM final approval. **Not merged. Not deployed. Registration remains disabled in production.**  
**Depends on:** permanent PWA/service-worker fix (draft PR #16) before any production frontend rebuild that could reintroduce cached navigation.

## 1. User flow

1. Operator adds the invitee’s email to the existing **Cloudflare Access** allow policy (outer gate).
2. Operator creates a single-use invitation with the CLI and delivers the plaintext code out-of-band (Signal / in person). Prefer `--code-file` (mode `0600`) so Cursor SSH / agent logs never capture the secret. Never paste production codes into tickets or Cursor chats.
3. Invitee opens `https://fashionrise.app` through Access, signs the Access challenge, then opens **Create account** (`/register`) from `/login`.
4. Invitee submits email (must match invite), username, optional display name, password, confirm password, and invitation code.
5. Backend validates `REGISTRATION_ENABLED`, locks the invitation, binds email, creates user+profile (`is_admin=false`), redeems the invite atomically, issues JWT tokens.
6. Client stores tokens, loads `/auth/me`, remounts Studio for the new user id (empty private draft / My Designs).

## 2. Threat model (summary)

| Threat | Control |
|---|---|
| Public internet registration | Cloudflare Access + AOP; Nginx still denies register until an approved allowlist change |
| Access member registering without invite | Server invitation ledger + `invitation_code` required |
| Invitation reuse / share | Single-use redeem + email bind + expiry + revoke |
| Token theft from DB | Only SHA-256 digest stored |
| Privilege escalation via register body | No role/admin fields accepted; `is_admin` forced false |
| Enumerating valid invites | Generic “not valid” / expired messages; no token echo |
| Race on redeem / revoke | Same `SELECT … FOR UPDATE` protocol for redeem and revoke |
| Concurrent register uniqueness | Flush/commit wrapped; recognized uniqueness → HTTP 409; loser invite stays pending |
| Rate-limit bypass via forged XFF | Default ignore client XFF; optional `TRUST_PROXY_HEADERS` + Nginx overwrite of `X-Real-IP` |
| Cross-account design leak | Owner checks + Studio remount keyed by `user.id` + IndexedDB keyed by `userId` |
| Accidental production enable | `REGISTRATION_ENABLED` defaults **false** |
| Destructive tests on production DB | Fail-closed `DATABASE_URL_TEST` guard (rejects missing/ambiguous/`fashionrise_beta`/same-as-app) |

## 3. Invite lifecycle

`pending → redeemed | revoked | expired`

- Create: high-entropy `token_urlsafe(32)`, store digest, deliver plaintext once via `--code-file` (preferred) or `--print-code` (local interactive only).
- Redeem: lock row, validate status + email, create user/profile, mark redeemed, commit.
- Revoke: unused only; same row lock as redeem; already-redeemed → conflict (does not report success).
- Inspect: CLI status never prints the token.

## 4. Operator provisioning

```bash
cd /opt/fashionrise/src/backend   # or local backend/
# After approved migration 004 and REGISTRATION_ENABLED=true in that environment:
mkdir -p /var/lib/fashionrise/invites && chmod 700 /var/lib/fashionrise/invites
# --code-file creates a NEW 0600 file only (refuses overwrite / symlinks).
python scripts/manage_invitations.py create person@example.com --hours 72 \
  --code-file /var/lib/fashionrise/invites/person.code
# Operator reads the file out-of-band; do not cat into shared logs/chat.
python scripts/manage_invitations.py status --email person@example.com
python scripts/manage_invitations.py revoke --id <uuid>
```

**Disposable migration smoke (never production):**

```bash
# Binds validation + Alembic execution to the same DATABASE_URL_TEST.
# Do NOT use bare `alembic` after a standalone preflight — that can still hit .env.
DATABASE_URL_TEST=postgresql+psycopg2://…/fashionrise_mig_v3b \
  python scripts/run_migration_smoke.py upgrade head
DATABASE_URL_TEST=…/fashionrise_mig_v3b \
  python scripts/run_migration_smoke.py downgrade 003
DATABASE_URL_TEST=…/fashionrise_mig_v3b \
  python scripts/run_migration_smoke.py upgrade 004
```

Production migrations remain the separately authorized `alembic upgrade/downgrade` path with the real `DATABASE_URL` / `backend/.env` after PM approval.

**Cloudflare Access:** In Zero Trust → Access → Applications → FashionRise, add the invitee’s email (or IdP group) to the existing allow policy. Do not broaden to “Everyone”. Do not disable Access.

**Out-of-band code delivery:** Share the one-time code through a channel the operator already trusts with the invitee. Do not email codes through this product (no mailer in scope).

## 5. Security boundaries

- Outer: Cloudflare Access + origin AOP.
- Inner: invitation ledger + registration gate.
- Nginx register allowlist is a **separate** activation step (`docs/deploy/PROPOSED-NGINX-REGISTER-ALLOWLIST.md`) — POST-only, exact path, suffix deny, default `/api/` deny preserved.
- AI / Gallery / uploads / public docs remain denied.

## 6. Deployment prerequisites (future; not this PR)

1. Merge + deploy PR #16 (PWA navigateFallback removed) so Access cannot be bypassed by cached HTML.
2. Merge WEB-V3B after PM security re-review.
3. Backup DB; apply Alembic `004` on production only with explicit approval.
4. Set `REGISTRATION_ENABLED=true` in the FashionRise API environment.
5. Apply the proposed Nginx register allowlist; `nginx -t` + reload.
6. Restart **only** `fashionrise-api`.
7. Create a test invitation for a non-production email and verify register → Studio isolation.
8. Keep a rollback plan: set `REGISTRATION_ENABLED=false`, restore Nginx deny for register, retain migration (invites become inert).

## 7. Test matrix

| Area | Coverage |
|---|---|
| Gate default off | Backend test forces disabled → 403 |
| Happy path invite register | Backend + frontend authApi |
| Missing / invalid / expired / revoked / reused / wrong-email | Backend |
| Duplicate email/username | Backend |
| Concurrent redeem + concurrent different-invite uniqueness | Backend threads on live disposable Postgres |
| Revoke-then-redeem / redeem-then-revoke orderings | Backend |
| Atomic failure does not consume invite | Backend |
| Login still works | Backend |
| Design isolation across two invited users | Backend |
| Test DB fail-closed (no connection) | `test_test_db_guard` |
| Trusted rate-limit IP | `test_rate_limit_ip` |
| Secure `--code-file` delivery (new-file only, no symlink, revoke on failure) | `test_manage_invitations_code_file` |
| Bound migration smoke runner (no silent `.env` target) | `test_migration_smoke_runner` + disposable DB |
| Login ↔ Register navigation | Frontend |
| Validation / confirm password / double-submit | Frontend |
| Uncertain register → sign-in recovery (no duplicate POST) | Frontend |
| Register/login `/auth/me` failure clears half-session | Frontend |
| Account switch clears identity before new session | Frontend AuthProvider |
| Studio remount on user id | `App.accountIsolation` |
| IndexedDB per-user isolation | `localDraftStore.isolation` |

## 8. Verification (final safety corrections)

**Test database / migration smoke safety evidence**

| Check | Result |
|---|---|
| `DATABASE_URL_TEST` | Explicit `fashionrise_test` / `fashionrise_mig_v3b` (localhost) |
| Reject missing `DATABASE_URL_TEST` for pytest | Exit code **2** — refuses create/drop |
| Reject `fashionrise_beta` as test target | Exit code **2** (no connection) |
| `run_migration_smoke.py` missing TEST URL | Exit code **2** (no Alembic spawn) |
| `run_migration_smoke.py` beta name | Exit code **2** (no Alembic spawn) |
| Bound smoke with ambient `DATABASE_URL` → beta name | Still migrates **only** `fashionrise_mig_v3b` |
| Local prod DB present? | `fashionrise_beta` count **0** on this agent host |

**Rate-limit activation (proposed; not applied)**

With Nginx overwriting `X-Real-IP`/`X-Forwarded-For` to `$remote_addr` on **login, refresh, logout, me, register, and designs**, and `TRUST_PROXY_HEADERS=true`, SlowAPI buckets by real client IP — users do **not** share a single `127.0.0.1` login bucket. Leaving `TRUST_PROXY_HEADERS=false` behind local Nginx would share one bucket; that must not be the activated production posture.

**Suites**

| Gate | Result |
|---|---|
| Guard / rate-limit / code-file / migration-runner unit | **23 / 23 pass** (no DB) |
| Invite + concurrency (`test_invite_registration`) | **19 / 19 pass** on `fashionrise_test` |
| Full backend `pytest` | **145 pass**, **1 pre-existing unrelated fail** (`test_cli_default_is_dry_run`) |
| Bound Alembic clean `0→head` on `fashionrise_mig_v3b` | **Pass** → `004` |
| Bound Alembic `004→003→004` | **Pass** |
| Frontend `npm test` | **195 / 195 pass** (35 files) |
| `npm run lint` | Pass (3 pre-existing oxlint warnings) |
| `tsc -b` + `npm run build` | Pass |

## 9. Rollback strategy

- Flip `REGISTRATION_ENABLED=false` (immediate app-level stop).
- Restore Nginx `return 403` for `/api/v1/auth/register`.
- Do not need to drop `004` unless PM requests; unused invites simply cannot redeem.
- Frontend `/register` can remain (will fail closed) or be hidden in a follow-up.

## 10. Limitations

- No email delivery of invites.
- No admin HTTP API for invites (CLI only).
- Username charset limited to `[A-Za-z0-9_]`.
- Production activation blocked until PR #16 + PM deploy approval.
