# FashionRise — Invite Registration Activation

**Purpose:** Concise operator procedure to turn the **already-merged** invite registration product (PRs #19/#20 + this product PR) into a working user experience.  
**Does not authorize itself.** Do not change production until Technical PM / operator approval names this procedure.

**Out of scope here:** Cloudflare Access JWT enablement, Option B `real_ip`, `TRUST_PROXY_HEADERS=true`, Stage D security hardening cycles.

---

## Working product journey (target)

1. Invitee opens FashionRise (Cloudflare Access still required).
2. Chooses **Create account** on `/login`.
3. Enters email, username, password, invitation code (optional deep-link `?email=&code=`).
4. Completes registration → lands in Studio.
5. Creates and saves a design.
6. Logs out and logs back in — design remains.
7. A second invited account cannot see the first account’s designs.

---

## What must change in production (ordered)

| Step | Change | Notes |
|---|---|---|
| **1. Backend deploy** | Checkout approved GitHub SHA containing registration code (at least `4aed16ce…` + this product PR once merged) into `/opt/fashionrise/src` | Keep `REGISTRATION_ENABLED=false` for the first restart. Frontend release root unchanged. |
| **2. Migration `004`** | `alembic upgrade 004` on `fashionrise_beta` after backup | Creates `registration_invitations`. Existing user + schema `003` data preserved. |
| **3. Nginx register allowlist** | Replace exact `return 403` on `/api/v1/auth/register` with **POST-only** proxy to `127.0.0.1:8010` | See `docs/deploy/PROPOSED-NGINX-REGISTER-ALLOWLIST.md` register location. Keep suffix deny. Do **not** open general `/api/`. |
| **4. Backend gate on** | Set `REGISTRATION_ENABLED=true` in FashionRise `.env` and restart `fashionrise-api` | Confirm `/health` and existing login still work. |
| **5. Frontend gate on** | Rebuild `web-ui` with `VITE_REGISTRATION_UI_ENABLED=true` and switch Nginx root to the new release | Create Account appears; `/register` serves the form. Preserve Access-safe SW assertions (`npm run build` / `check:sw`). |
| **6. Provision invite** | Add invitee email to Cloudflare Access policy; `manage_invitations.py create … --code-file` | Deliver code out-of-band. Never paste production codes into chat. |
| **7. Accept** | Controlled second-user walkthrough of the journey above | Also verify expired/used codes and duplicate email/username messaging. |

### Rollback (if anything fails)

1. `REGISTRATION_ENABLED=false` + restart API.  
2. Restore Nginx register **deny**.  
3. Optional: roll frontend root back to prior release (UI gate off).  
4. Leave Alembic at **`004`** (do not downgrade after redemptions).  
5. Cloudflare Access / AOP unchanged.

---

## Residual risk (acknowledged, not a hard product blocker)

Without Option B `real_ip` + trusted proxy headers, SlowAPI may continue to bucket many Access clients under the Cloudflare edge IP for rate limits. **Invite ledger + Access + AOP + Nginx path allowlist** still gate account creation. Per-client rate-limit IP hardening remains a **separate** follow-up, not required to deliver the registration UX.

---

## Pre-activation verification (isolated / disposable only)

- Backend invite suite with `DATABASE_URL_TEST` → disposable DB (never `fashionrise_beta`).
- Frontend vitest for Register/Login gates and error mapping.
- Optional: `run_migration_smoke.py` on `fashionrise_mig_v3b` for `004`.

---

## Related docs

- Product QA matrix: `docs/WEB-V3B-INVITE-REGISTRATION-QA.md`
- Nginx proposal: `docs/deploy/PROPOSED-NGINX-REGISTER-ALLOWLIST.md`
- Security preflight (Checkpoint A flags-off deploy): `docs/deploy/SECURITY-INTEGRATION-PREFLIGHT.md` — useful for the backend code rollout step; **registration enablement is this document**, not Checkpoint A.
