# WEB-V3B — Invite-Only Beta Registration

**Branch:** `cursor/web-v3b-invite-registration-77c6`  
**Status:** security-amendment complete — awaiting Technical PM re-review. **Not merged. Not deployed. Registration remains disabled in production.**  
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
mkdir -p /root/.fashionrise-invites && chmod 700 /root/.fashionrise-invites
python scripts/manage_invitations.py create person@example.com --hours 72 \
  --code-file /root/.fashionrise-invites/person.code
# Operator reads the file out-of-band; do not cat into shared logs/chat.
python scripts/manage_invitations.py status --email person@example.com
python scripts/manage_invitations.py revoke --id <uuid>
```

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
| Secure `--code-file` delivery | `test_manage_invitations_code_file` |
| Login ↔ Register navigation | Frontend |
| Validation / confirm password / double-submit | Frontend |
| Uncertain register → sign-in recovery (no duplicate POST) | Frontend |
| Register/login `/auth/me` failure clears half-session | Frontend |
| Account switch clears identity before new session | Frontend AuthProvider |
| Studio remount on user id | `App.accountIsolation` |
| IndexedDB per-user isolation | `localDraftStore.isolation` |

## 8. Verification (security amendment)

**Test database safety evidence**

| Check | Result |
|---|---|
| `DATABASE_URL_TEST` | Explicit `fashionrise_test` (localhost) |
| Reject missing `DATABASE_URL_TEST` | Exit code **2** — refuses create/drop |
| Reject `fashionrise_beta` as test target | Exit code **2** (no connection) |
| `verify_migration_target.py` on `fashionrise_mig_v3b` | `migration_target=safe` |
| Local prod DB present? | `fashionrise_beta` count **0** on this agent host |

**Suites**

| Gate | Result |
|---|---|
| Guard / rate-limit / code-file unit | **13 / 13 pass** (no DB) |
| Invite + concurrency (`test_invite_registration`) | **19 / 19 pass** on `fashionrise_test` |
| Full backend `pytest` | **135 pass**, **1 pre-existing unrelated fail** (`test_cli_default_is_dry_run`) |
| Alembic clean `0→head` on `fashionrise_mig_v3b` | **Pass** → `004` |
| Alembic `004→003→004` | **Pass** |
| Frontend `npm test` | **195 / 195 pass** (35 files) |
| `npm run lint` | Pass (3 pre-existing oxlint warnings) |
| `tsc -b` + `npm run build` | Pass |
| Browser SPA smoke (Playwright, `serve -s` dist) | `/login` → Create account → `/register` with Invitation code — **PASS**. Screenshot: `/opt/cursor/artifacts/screenshots/playwright-register.png` |

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
