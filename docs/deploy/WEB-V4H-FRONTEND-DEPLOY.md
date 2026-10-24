# WEB-V4H frontend-only production deploy

**Result:** **SUCCESS**  
**Authorized by:** Operator approval recorded on GitHub Issue [#43](https://github.com/perielad2-netizen/FashionRise/issues/43)  
**Merged PR:** [#45](https://github.com/perielad2-netizen/FashionRise/pull/45)  
**Approved / deployed SHA:** `4f332a62b7fbfab70b882f1018d73ca8ca0b33fd`  
**Deployed at (UTC):** 2026-10-24T18:15:05Z → activated ~18:15:40Z  

## Scope

Frontend-only isolated release. **No** backend/worker restart, migrations, Nginx routing/allowlist/TLS/Access/AOP changes, DB writes, paid AI, Issue #42, or Magic pose PR #41 deploy.

## Preflight (observed)

| Check | Result |
|---|---|
| GitHub `main` | `4f332a62…` (merge of PR #45) |
| Active Nginx HTTPS root (before) | `/var/www/fashionrise/releases/350a3b7e` |
| Previous FE REVISION | `350a3b7eeea0adb09da2cf0c2306415471069501` |
| `fashionrise-api` / `fashionrise-ai-worker` / `nginx` | active / active / active |
| Backend + worker checkout | `2cbc1ad04e5bfc01d1d356c92398e26e3014afe9` |
| Alembic | **`005`** (read-only) |
| Disk | 78G free on `/` |
| Drift vs expected baseline | **None material** |

## Build (isolated worktree)

Path: `/tmp/fashionrise-v4h-fe-build` @ `4f332a62…` (not `/opt/fashionrise/src`).

| Gate | Result |
|---|---|
| `VITE_API_BASE_URL` | `/api/v1` |
| `VITE_REGISTRATION_UI_ENABLED` | `true` |
| `VITE_MAGIC_UI_ENABLED` | `true` |
| `npm ci` | ok |
| Vitest | **347/347** |
| oxlint | warnings only (no errors) |
| `tsc -b` | ok |
| production build | ok |
| `check:sw` | `ok=true` · `navigation_route=false` · `create_handler_bound_to_url=false` · `html_precache_count=0` |
| Library croquis | **10** PNGs under `models/library/` |
| Legacy croquis | `female_model.png`, `male_model_display.png`, `male_model.png` |
| Branding | `branding/fashion_rise_*.png` + icons present |
| Paid OpenAI | **0** |

`sw.js` sha256: `ce206d93e0c964457595c57b37ebe2c69667ad4954347a64861c0292476ab376`

## Install & activate

| Item | Path / value |
|---|---|
| New release | `/var/www/fashionrise/releases/4f332a62` |
| `REVISION` | full SHA `4f332a62b7fbfab70b882f1018d73ca8ca0b33fd` |
| Previous release preserved | `/var/www/fashionrise/releases/350a3b7e` |
| Backup | `/var/backups/fashionrise/v4h-fe-deploy-20261024T181505Z` |
| Nginx change | **only** HTTPS `root` → `…/releases/4f332a62` (ACME root untouched) |
| `nginx -t` | syntax ok / test successful |
| `systemctl reload nginx` | ok |
| Backend/worker PIDs | **unchanged** (35739 / 35740; started 2026-10-24 06:36:33 UTC) |

## Post-activate verification (observed)

| Check | Result |
|---|---|
| Active root | `/var/www/fashionrise/releases/4f332a62` |
| Installed REVISION | matches approved SHA |
| SW live assertions | no NavigationRoute / createHandlerBoundToURL / HTML precache |
| Local origin without client cert | **HTTP 400** (AOP) |
| No-session Access `/studio` | **HTTP 302** → Cloudflare Access login |
| `/health` / `/ready` | ok / ready+database ok |
| Backend/worker SHA | still `2cbc1ad0` |
| Alembic | still **`005`** |
| AI / fabrics Nginx deny | still present (`return 403`) |
| IndexedDB / saved designs | not touched |

## Frontend-only rollback

```bash
sudo bash /var/backups/fashionrise/v4h-fe-deploy-20261024T181505Z/ROLLBACK.sh
# or: set Nginx root back to /var/www/fashionrise/releases/350a3b7e ; nginx -t ; systemctl reload nginx
```

Does **not** restart API/worker or touch the database.

## Outstanding (operator)

1. **Authenticated production acceptance of WEB-V4H on a real tablet** (immersive toolbar, Exit, Focus restore, Fit Page/Width, zoom, pinch — physical device; emulation is not acceptance).
2. Issue #42 Front/Back croquis — backlog (not started).
3. Magic pose PR #41 — still not deployed; visual pose NOT accepted.
4. Docs draft PR #44 — do not auto-merge.
5. Expired Access session check — still PENDING.

## Explicit non-actions

No Magic BE/worker deploy · no migrations · no DB content changes · no secrets/API config changes · no service restarts · no paid OpenAI · no IndexedDB clear · no Issue #42 · no merge of docs PR #44.
