# P0 #136 — Studio gates missing after FE `6ec73ba2` deploy

**Status:** Phase A/B/C complete offline · **no production mutation** · STOP for Technical PM  
**Paid AI:** 0 · **BE/worker:** untouched `6cc317ec` · Alembic `011`  
**Branch:** `cursor/web-incident-136-vite-flags-77c6` · PR #137

## Phase A — Compiled gate diagnosis (immutable releases)

Inspected production `index-*.js` for constant-folded helpers:

| Gate | Detection | **live `6ec73ba2`** | **rollback `ebcb1cc7`** | known-good `69b83c01` |
|---|---|---|---|---|
| `VITE_STUDIO_FRONT_BACK_ENABLED` | `frontBackEnabled??H()` → `H(){return!0/!1}` | **OFF (`!1`)** | **OFF (`!1`)** | **ON (`!0`)** |
| `VITE_STUDIO_DUAL_MAGIC_ENABLED` | hook `a=H(),o=D()` next helper | **OFF** | **OFF** | **ON** |
| `VITE_MAGIC_UI_ENABLED` | `Ze=M()` beside magic phase busy flag | **OFF** | **OFF** | **ON** |
| `VITE_REGISTRATION_UI_ENABLED` | `/register` element gate helper | **OFF** | **OFF** | **OFF** |

`BUILD_ENV.txt`: missing on `6ec73ba2` / `ebcb1cc7` / `bfbdd03f-decimal`; present on `69b83c01`/`af1ddbb5` with MAGIC/FRONT_BACK/DUAL=`true`, REGISTRATION=`false`.

**Build procedure defect:** #134 clean-worktree build set only `VITE_API_BASE_URL` + `VITE_BUILD_SHA`. No `web-ui/.env.production` on the build host (`/opt/fashionrise/web-ui/.env.production` absent; local `.env.production` gitignored). Gates defaulted false at compile time. #134 source did **not** remove the gate modules.

**Restoring draft…:** `useStudioEditor` boot calls `documentForCloud` → `serializeStudioDraftDocument`, which **throws** on V2 drafts when Front/Back is off. The boot async IIFE had **no try/catch**, so `saveStatus` stayed `'restoring'`. **Do not** clear site data / force V2→V1 / overwrite cloud.

## Phase B — Rollback preparedness (NOT executed)

| Item | Value |
|---|---|
| Command (ready) | `bash /var/www/fashionrise/releases/6ec73ba2/ROLLBACK.sh` → `ebcb1cc7` |
| Prep record | `/var/backups/fashionrise/incident-136-rollback-prep-20261030T103659Z/` |
| BE/worker | unchanged |
| **Warning** | `ebcb1cc7` compiled gates are **also OFF** — rollback restores prior Fill tip but **will not** restore Front/Back or Magic UI |
| Owner auth | **required before execute** |

## Phase C — Forward release candidate (not activated)

Allowlist from known-good `BUILD_ENV.txt` (not invented from `.env.production.example`):

```
VITE_API_BASE_URL=/api/v1
VITE_REGISTRATION_UI_ENABLED=false
VITE_MAGIC_UI_ENABLED=true
VITE_STUDIO_FRONT_BACK_ENABLED=true
VITE_STUDIO_DUAL_MAGIC_ENABLED=true
VITE_BUILD_SHA=6ec73ba26ee5b8c25b29a77d31050942af4c6c6d
```

| Deliverable | Result |
|---|---|
| Offline rebuild of `web-ui` tree `0709aa71…` | Compiled FRONT_BACK/DUAL/MAGIC **`!0`**; REG **`!1`** |
| `assert-prod-vite-flags.mjs` | Wired into `npm run build`; writes `dist/BUILD_ENV.txt`; fails if gates default off |
| Restore boot harden | try/catch around fingerprint serialize; V2 kept on canvas as `local-only`; no cloud overwrite |
| Regression test | `useStudioEditor.restoreBoot.test.tsx` |
| Vitest | **661 passed / 6 known baseline fails** (5× StudioPage beta-notices + `draftPersistence` clearBackIntent) |
| `tsc` / lint / prod build + SW Access-safe + `/api/v1` | **PASS** |
| Production activate | **NOT done** |

## Recommendation for Technical PM / owner

1. **Preferred:** Authorize FE-only deploy of rebuilt `6ec73ba2` tree **with** the allowlist above (keeps #127 extended paper + restores Studio gates). Validate nonempty release + `BUILD_ENV.txt` + compiled `return!0` **before** symlink.
2. **Not sufficient as gate fix:** symlink rollback to `ebcb1cc7`.
3. Keep #135 PAUSED; #127 OPEN until owner mobile QA after gates restored.
4. No paid AI / BE restart / migration.

## Live snapshot (unchanged this turn)

- `current` → `/var/www/fashionrise/releases/6ec73ba2`
- BE/worker `6cc317ec` · Alembic `011`
