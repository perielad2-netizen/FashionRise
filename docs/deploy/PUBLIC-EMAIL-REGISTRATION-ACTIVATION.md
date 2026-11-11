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

**Fail closed:** `REGISTRATION_MODE=public` without SMTP (`SMTP_HOST` + `SMTP_FROM_EMAIL`) keeps **effective mode closed**. Status payload reports the exact prerequisite.

---

## Working product journey (target)

1. Visitor opens `/login` and sees **Don't have an account? Create Account**.
2. Completes email / username / password (no invitation code).
3. Sees **Check your email** — no Studio session yet.
4. Opens the one-time link → `/verify-email?token=…` → Studio.
5. Logout / login with the same password works.
6. Google Sign-In and existing invited accounts continue unchanged.
7. New public users start with normal Stars; never admin / never unlimited.

---

## Exact safe production activation steps (ordered)

| Step | Change | Notes |
|---|---|---|
| **1. Backup DB** | Snapshot `fashionrise_beta` | Required before migration. |
| **2. Backend deploy** | Deploy approved SHA containing public registration | Keep `REGISTRATION_MODE` unset/closed for first restart. |
| **3. Migration `028`** | `alembic upgrade 028` | Adds `users.email_verified` (existing rows → `true`) + `email_verification_tokens`. |
| **4. Configure SMTP** | Set `EMAIL_DELIVERY_BACKEND=smtp`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM_EMAIL`, credentials, `SMTP_USE_TLS` | Use an existing provider / relay. Confirm a test message works from the API host. |
| **5. Nginx** | Ensure auth registration paths proxy to the API | Allow POST register + verify-email + resend-verification; GET registration/status. Extend the auth regex (same pattern as Google allowlist). See `docs/deploy/PROPOSED-NGINX-REGISTER-ALLOWLIST.md`. |
| **6. Flip mode** | `REGISTRATION_MODE=public` + restart `fashionrise-api` | Confirm `GET /api/v1/auth/registration/status` → `mode=public`, `registration_available=true`. |
| **7. Frontend** | Deploy SPA from the same product SHA (Create Account uses status; Vite flag may stay false) | Login logo unchanged. |
| **8. Accept** | Create account → verify email → login; duplicate email/username; invite_only still works if flipped back; Google login regression | Rate-limit smoke from a single IP. |

### Rollback

1. `REGISTRATION_MODE=closed` (or remove) + restart API.  
2. Optional: restore prior Nginx deny on register.  
3. Leave Alembic at **`028`** (do not downgrade after verifications).  
4. Existing users and balances unchanged.

---

## Production prerequisites (exact)

- SMTP delivery: `SMTP_HOST`, `SMTP_FROM_EMAIL` (plus username/password/TLS as required by the relay).
- Migration `028` applied.
- Nginx allows POST register + verify-email + resend-verification + GET registration/status.
- Public IAP purchasing/credit gates remain **OFF** unless separately approved.

---

## Related

- Invite activation (legacy): `docs/deploy/REGISTRATION-ACTIVATION.md`
- Project status: `docs/00-PROJECT-STATUS.md`
