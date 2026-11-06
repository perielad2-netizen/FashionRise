# FashionRise — PWA frontend rollout Stage A (prepare only)

**Status:** Stage A complete — **BLOCKED** for Stage B until draft PR #20 (registration UI gate) is approved and merged.  
**Date (UTC):** 2026-10-20  
**GitHub `main` verified:** `ceb10a4e67972e901a2a2c107df70d77c50ea2b8`  
**Candidate release SHA (gated):** `c017fa688c03172084b87f9c34301860a6c7869b` (PR #20)  
**Stage B:** NOT AUTHORIZED

## 1. Preflight PASS/FAIL

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | GitHub `main` SHA | **PASS** | `ceb10a4e` (PR #16 merge) |
| 2 | VPS `/opt/fashionrise/src` HEAD | **PASS** | `85b6561b…` clean `main` |
| 3 | Working tree / untracked | **PASS** | Clean porcelain; no unexpected tracked dirty files |
| 4 | Nginx frontend root | **PASS** | `root /var/www/fashionrise/releases/85b6561b;` |
| 5 | Active SW contents | **PASS (mitigated)** | Temporary hotfix `sw.js` (1581 B); navigations skipped; `sw.js.pre-incident-hotfix` preserved (had NavigationRoute + index.html) |
| 6 | Nginx fashionrise.app | **PASS** | AOP `ssl_verify_client on`; register `return 403`; AI/uploads/docs denied; auth+designs proxied to `:8010`; `sw.js`/`index.html` `Cache-Control: no-cache` |
| 7 | Cloudflare Access | **PASS** | Unauthenticated HTTPS → **302** to `*.cloudflareaccess.com` for `/login`, `/register`, `/sw.js` |
| 8 | AOP | **PASS** | Local HTTPS without client cert → **400** “No required SSL certificate was sent” |
| 9 | `fashionrise-api` | **PASS** | `active`; `127.0.0.1:8010`; `/health` → `{"status":"ok"}` |
| 10 | Alembic (read-only) | **PASS** | **`003 (head)`** on `fashionrise_beta` |
| 11 | Registration gate | **PASS (off)** | `REGISTRATION_ENABLED` unset in `.env` (defaults false); Nginx denies register |
| 12 | Disk / perms | **PASS** | 83G free on `/`; releases owned appropriately; backups present |
| 13 | Registration UX compatibility | **FAIL / BLOCKER** | Shipping `ceb10a4e` alone would show Create Account while signup cannot complete → draft **PR #20** |

No material drift from the expected production baseline. PickWise / CureCompass / other DBs untouched.

## 2. Registration UI decision

**Problem:** WEB-V3B on `main` always exposes Create Account + `/register`. Production cannot redeem invites (no `004`, Nginx 403, registration disabled).

**Fix (draft PR #20):** `VITE_REGISTRATION_UI_ENABLED` default **false** — hide link; `/register` → `/login`. Backend remains authoritative.

**Release rule:** Do **not** deploy `ceb10a4e` frontend alone. Deploy only after PR #20 merges (or equivalent). Keep `VITE_REGISTRATION_UI_ENABLED=false` for this PWA-only rollout.

## 3. Staging build (immutable candidate)

Prepared **off-VPS** (agent workspace), not written into `/var/www`:

| Item | Value |
|---|---|
| Source | `c017fa688c03172084b87f9c34301860a6c7869b` |
| Staging path | `/tmp/fashionrise-frontend-stage/c017fa688c03172084b87f9c34301860a6c7869b/` |
| Env | `VITE_API_BASE_URL=/api/v1`, `VITE_REGISTRATION_UI_ENABLED=false` |
| `npm ci` / test / lint / tsc / build | All **PASS** (205 tests; build embeds SW assert) |
| `dist/sw.js` sha256 | `a51964e6acf2f2f7bd0c2c62caa9ecc49a8cdca5e8cfcc2944263a8eae43007e` |
| HTML precache | **0** |
| `NavigationRoute` / `createHandlerBoundToURL` | **absent** |
| Precache entries | 19 static assets |
| Secret scan | Only benign `password=` form-field string in JS bundle |

Proposed production release directory (Stage B only):  
`/var/www/fashionrise/releases/c017fa68` (or full SHA), switched via Nginx `root` change — **not performed**.

## 4. Service-worker upgrade notes

| Topic | Assessment |
|---|---|
| Hotfix → permanent | New Workbox SW has no HTML navigation fallback; Nginx already `no-cache` on `/sw.js` and `/index.html` |
| Client update | `registerType: autoUpdate` + `skipWaiting`/`clientsClaim` in generateSW config |
| IndexedDB | SW change does not clear IDB; **do not** instruct Clear site data |
| Rollback SW | Must restore hotfix `sw.js` (or entire `85b6561b` tree with hotfix), **never** restore `sw.js.pre-incident-hotfix` alone |
| CF Access after deploy | Must re-validate with real Access session + expired/absent session (Stage B) |

No Nginx/Cloudflare policy change required for Stage A. Optional Stage B note: keep `location = /sw.js` `Cache-Control: no-cache` (already present).

## 5. Rollback preparation (Stage B)

Preserve (do not delete):

- Active: `/var/www/fashionrise/releases/85b6561b` (includes hotfix `sw.js` + `sw.js.pre-incident-hotfix`)
- Backup: `/var/backups/fashionrise/web-v3a-deploy-20261020T124335Z/` (`ROLLBACK.sh`, nginx snapshot, DB dump, hotfix notes)
- Prior releases: `f8a5b22`, `9db1fa`, `6df327ba`

**Rollback actions (if Stage B fails):**

1. Set Nginx `root` back to `/var/www/fashionrise/releases/85b6561b`.
2. `nginx -t && systemctl reload nginx` only if config edited.
3. Confirm hotfix `sw.js` still present (navigations not handled).
4. Do **not** restart API / migrate DB for frontend rollback.
5. Confirm Access 302 without session; login works with valid Access.

## 6. Intended Stage B procedure (NOT executed)

1. Merge PR #20; re-verify SHA.
2. Recheck VPS health, Alembic `003`, registration still off.
3. Upload staging `dist/` to new release dir under `/var/www/fashionrise/releases/<sha>/` with `REVISION` file.
4. Backup current nginx site file + note active root.
5. Atomically point `root` to new release; `nginx -t`; reload if needed.
6. Verify `/sw.js` bytes/hash match staging; no NavigationRoute; no HTML precache.
7. Acceptance: Access valid/absent/expired; login; Studio draft; My Designs; export; offline retry.
8. Confirm Create Account **hidden**; `/register` redirects to login.
9. Roll back immediately on any gate failure.

Backend restart: **not required**. Migrations: **none**.

## 7. Outstanding blockers

1. **PR #20 must merge** before any production frontend switch.
2. Stage B PM authorization still required.
3. Post-deploy expired Access validation still outstanding (cannot claim from local Playwright alone).
4. WEB-V3B activation remains a **separate** milestone.
