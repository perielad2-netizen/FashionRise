# FashionRise — PWA frontend rollout Stage B (executed)

**Result:** **SUCCESS** (frontend-only).  
**Date (UTC):** 2026-10-20T16:32Z  
**GitHub `main`:** `8c6a391a0d5bb3acc5e697e63c47e3ec242ec9fd`  
**Live frontend release:** `/var/www/fashionrise/releases/8c6a391a`  
**Backend unchanged:** `/opt/fashionrise/src` @ `85b6561b…` · Alembic **`003`** · `fashionrise-api` **active**

## Pre-switch recheck

All Stage A safety conditions reconfirmed before switch: Nginx root was `85b6561b`, hotfix `sw.js` present (`24e572df…`), AOP on, Access 302 without session, register Nginx deny, Alembic `003`, registration unset/false, 83G free disk.

## Build

| Item | Value |
|---|---|
| Source | Clean worktree at `8c6a391a…` (not prior `c017fa68` staging) |
| Env (build-time) | `VITE_API_BASE_URL=/api/v1`, `VITE_REGISTRATION_UI_ENABLED=false` |
| `npm ci` / test / lint / build | PASS · **205** tests · SW assert embedded **ok** |
| `dist/sw.js` sha256 | `a51964e6acf2f2f7bd0c2c62caa9ecc49a8cdca5e8cfcc2944263a8eae43007e` |
| HTML precache / NavigationRoute / createHandlerBoundToURL | **0 / absent / absent** |
| Secret patterns in artifacts | none |

## Switch

| Step | Outcome |
|---|---|
| Backup | `/var/backups/fashionrise/web-pwa-stageb-20261020T163237Z/` (+ `ROLLBACK.sh`, prior nginx, hotfix SW copy) |
| Previous root preserved | `/var/www/fashionrise/releases/85b6561b` (hotfix intact) |
| New release installed | `/var/www/fashionrise/releases/8c6a391a` · `REVISION` = full SHA |
| Installed SW hash | matches build |
| Nginx `root` | `85b6561b` → **`8c6a391a`** |
| `nginx -t` + reload | OK |
| API restart | **not performed** |
| Migrations | **not performed** |

## Verification

### Artifact / SW (PASS)

- Live FS + origin (AOP client cert) `sw.js` sha256 = build hash.
- No NavigationRoute / createHandlerBoundToURL / index.html in SW.
- `/sw.js` and `/index.html` → `Cache-Control: no-cache`.
- Headless local dist: SW registers; `/studio` document navigation `fromCache=false`; Create Account hidden; `/register` → `/login`.

### Cloudflare Access / AOP

| Check | Result |
|---|---|
| No Access session: `/login`, `/register`, `/studio`, `/studio/designs`, `/sw.js` | **302** to Cloudflare Access (**PASS**) |
| Origin without client cert | **400** AOP (**PASS**) |
| Origin with AOP client cert: SPA + SW | **200** (**PASS**) |
| Valid Access session browser login/Studio | **INCOMPLETE** — no Access credentials in this agent environment |
| Genuinely expired Access session | **INCOMPLETE** — not testable here |

### Application API (partial)

| Check | Result |
|---|---|
| `fashionrise-api` health | **PASS** `{"status":"ok"}` |
| Login route reachable (bad password) | **401** unauthorized (**PASS** path) |
| Designs unauthenticated | **401** (**PASS**) |
| Existing-user sign-in / draw / My Designs / Export / draft recovery | **INCOMPLETE** — requires valid Access + app session |

### Registration boundary (PASS)

| Check | Result |
|---|---|
| Create Account on Login (built SPA) | **hidden** |
| `/register` SPA | **redirects to `/login`** |
| Nginx `POST /api/v1/auth/register` | **403** |
| `REGISTRATION_ENABLED` | unset (defaults false) |
| Alembic | **`003`** |
| Invitations created | none |

## Rollback readiness

- Target: `/var/www/fashionrise/releases/85b6561b` **with hotfix SW** (`24e572df…`).
- Script: `/var/backups/fashionrise/web-pwa-stageb-20261020T163237Z/ROLLBACK.sh`
- Do **not** restore `sw.js.pre-incident-hotfix`.
- Do **not** clear IndexedDB.

## Outstanding (operator)

1. Valid Cloudflare Access session: login, Studio, drafts, My Designs, reopen, PNG export, offline retry.
2. Genuinely expired Access session: confirm network document (not SW shell).
3. Optional: confirm installed clients update from hotfix SW → permanent Workbox SW.

## Next action

Operator acceptance of items above. Separate PM approval still required for WEB-V3B registration activation (migration `004`, Nginx allowlist, invitations, `VITE_REGISTRATION_UI_ENABLED=true`).
