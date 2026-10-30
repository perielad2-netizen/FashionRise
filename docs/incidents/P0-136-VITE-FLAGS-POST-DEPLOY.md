# P0 #136 — Studio gates missing after FE `6ec73ba2` deploy

**Status:** Forensics complete · **no production mutation this turn** · awaiting owner authorization for forward rebuild deploy (rollback to `ebcb1cc7` will **not** restore gates).  
**Paid AI:** 0 · **BE/worker:** untouched `6cc317ec` · Alembic `011`

## Owner symptoms (after FE `6ec73ba2`)

- Front/Back icon missing in Create/Studio
- Magic shows **Soon**
- Draft status stuck on **Restoring draft…**

## Compiled-bundle forensics (authoritative)

Inspected production `index-*.js` for `frontBackEnabled??<helper>()` and the constant-folded helper body:

| Release | `frontBack` helper | Immediate next gate (`dualMagic` in hook) | `BUILD_ENV.txt` |
|---|---|---|---|
| **`6ec73ba2` (live)** | **`return!1` (OFF)** | **`return!1` (OFF)** | missing |
| **`ebcb1cc7` (rollback target)** | **`return!1` (OFF)** | **`return!1` (OFF)** | missing |
| `bfbdd03f-decimal` | `return!1` (OFF) | `return!1` (OFF) | missing |
| `69b83c01` / `af1ddbb5` / `31c1de01` | `return!0` (ON) | `return!0` (ON) | `VITE_MAGIC_UI_ENABLED=true` · `VITE_STUDIO_FRONT_BACK_ENABLED=true` · `VITE_STUDIO_DUAL_MAGIC_ENABLED=true` |

**Conclusion:** #134 source did not remove the gates; the **clean worktree production build** only set `VITE_API_BASE_URL` + `VITE_BUILD_SHA`, so Vite constant-folded `isStudioFrontBackEnabled` / related gates to **false**. The same defect is already present in immutable `ebcb1cc7` / `bfbdd03f-decimal` artifacts (no `BUILD_ENV.txt`). Rolling the symlink back to `ebcb1cc7` alone **cannot** restore Front/Back or Magic UI.

Owner “worked before `6ec73ba2`” is consistent with a **service-worker / older cached good bundle** (e.g. `69b83c01` lineage) being replaced when `6ec73ba2` activated — not with `ebcb1cc7` itself having gates on.

## Draft “Restoring…” coupling

`useStudioEditor` boots with `saveStatus='restoring'` and has **no try/catch** around `restoreStudioDraft` → `documentForCloud` / serialize. With Front/Back compiled OFF, `serializeStudioDraftDocument` **rejects V2 drafts**; an uncaught throw leaves the label stuck. **Do not** clear site data, force V2→V1, or overwrite cloud drafts.

## Approved flag allowlist (from known-good releases + `.env.production.example`)

```
VITE_API_BASE_URL=/api/v1
VITE_REGISTRATION_UI_ENABLED=false
VITE_MAGIC_UI_ENABLED=true
VITE_STUDIO_FRONT_BACK_ENABLED=true
VITE_STUDIO_DUAL_MAGIC_ENABLED=true
```

Dual Magic `true` matches post-`69b83c01` production `BUILD_ENV.txt` records (not invented). Early Front/Back-only release `4589a62d` had Dual Magic `false`; later accepted production builds re-enabled it.

## Mitigation plan (needs explicit owner auth before any symlink change)

1. **Preferred:** Rebuild accepted Fill source tree `6ec73ba2` (`web-ui` tree `0709aa71…`) with the allowlist above + `VITE_BUILD_SHA=6ec73ba2…`, run new `assert-prod-vite-flags.mjs`, verify compiled `frontBack` helper `return!0`, ship new immutable release dir, activate only after nonempty validation. Keeps #127 extended paper.
2. **Not sufficient:** `ROLLBACK.sh` → `ebcb1cc7` (gates still OFF).
3. **Emergency only (loses #127 paper + later fill fixes):** activate an older flagged release such as `69b83c01` — only if owner explicitly accepts feature rollback scope.

## Engineering follow-ups on branch `cursor/web-incident-136-vite-flags-77c6`

- `web-ui/scripts/assert-prod-vite-flags.mjs` + wire into `npm run build`
- Writes `dist/BUILD_ENV.txt` (booleans / routes only) for release forensics
- Docs / status updates; **STOP before production activate**

## Live state snapshot (forensics)

- `current` → `/var/www/fashionrise/releases/6ec73ba2`
- BE/worker `6cc317ec` · Alembic `011` · Access/AOP unchanged
- `ebcb1cc7` immutable rollback artifact retained
- Backup metadata: `/var/backups/fashionrise/incident-136-*`
- **#135 Create My Croquis:** PAUSED
- **#127:** remains OPEN (Fill paper accepted; owner mobile QA still required after gates restored)
