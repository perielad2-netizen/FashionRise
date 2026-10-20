# WEB-V3B — Invite-Only Beta Registration

**Branch:** `cursor/web-v3b-invite-registration-77c6`  
**Status:** implementation complete for Technical PM review. **Not merged. Not deployed. Registration remains disabled in production.**  
**Depends on:** permanent PWA/service-worker fix (draft PR #16) before any production frontend rebuild that could reintroduce cached navigation.

## 1. User flow

1. Operator adds the invitee’s email to the existing **Cloudflare Access** allow policy (outer gate).
2. Operator creates a single-use invitation with the CLI and delivers the plaintext code out-of-band (Signal / in person). Never paste production codes into tickets or Cursor chats.
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
| Race on redeem | `SELECT … FOR UPDATE` + single transaction |
| Cross-account design leak | Existing owner checks + Studio remount keyed by `user.id` + IndexedDB keyed by `userId` |
| Accidental production enable | `REGISTRATION_ENABLED` defaults **false** |

## 3. Invite lifecycle

`pending → redeemed | revoked | expired`

- Create: high-entropy `token_urlsafe(32)`, store digest, print plaintext once.
- Redeem: lock row, validate status + email, create user/profile, mark redeemed, commit.
- Revoke: unused only.
- Inspect: CLI status never prints the token.

## 4. Operator provisioning

```bash
cd /opt/fashionrise/src/backend   # or local backend/
# After approved migration 004 and REGISTRATION_ENABLED=true in that environment:
python scripts/manage_invitations.py create person@example.com --hours 72
python scripts/manage_invitations.py status --email person@example.com
python scripts/manage_invitations.py revoke --id <uuid>
```

**Cloudflare Access:** In Zero Trust → Access → Applications → FashionRise, add the invitee’s email (or IdP group) to the existing allow policy. Do not broaden to “Everyone”. Do not disable Access.

**Out-of-band code delivery:** Share the one-time code through a channel the operator already trusts with the invitee. Do not email codes through this product (no mailer in scope).

## 5. Security boundaries

- Outer: Cloudflare Access + origin AOP.
- Inner: invitation ledger + registration gate.
- Nginx register allowlist is a **separate** activation step (`docs/deploy/PROPOSED-NGINX-REGISTER-ALLOWLIST.md`).
- AI / Gallery / uploads / public docs remain denied.

## 6. Deployment prerequisites (future; not this PR)

1. Merge + deploy PR #16 (PWA navigateFallback removed) so Access cannot be bypassed by cached HTML.
2. Merge WEB-V3B after PM security review.
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
| Concurrent redeem | Backend threads on live Postgres |
| Atomic failure does not consume invite | Backend |
| Login still works | Backend |
| Design isolation across two invited users | Backend |
| Login ↔ Register navigation | Frontend |
| Validation / confirm password / double-submit | Frontend |
| Studio remount on user id | App `UserScopedStudio` |

## 8. Rollback strategy

- Flip `REGISTRATION_ENABLED=false` (immediate app-level stop).
- Restore Nginx `return 403` for `/api/v1/auth/register`.
- Do not need to drop `004` unless PM requests; unused invites simply cannot redeem.
- Frontend `/register` can remain (will fail closed) or be hidden in a follow-up.

## 9. Limitations

- No email delivery of invites.
- No admin HTTP API for invites (CLI only).
- Username charset limited to `[A-Za-z0-9_]`.
- Production activation blocked until PR #16 + PM deploy approval.
