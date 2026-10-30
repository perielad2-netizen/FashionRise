# P0 #136 — Studio gates missing after FE `6ec73ba2` deploy

**Status:** Corrections A/B/C on PR #137 · **no production mutation** · STOP for final Technical PM  
**Paid AI:** 0 · **BE/worker:** untouched `6cc317ec` · Alembic `011`  
**Branch:** `cursor/web-incident-136-vite-flags-77c6` · PR [#137](https://github.com/perielad2-netizen/FashionRise/pull/137) · tip `2dfcaba0a97059adddceaa3ae8e0bee000fb32df`  
**Release runbook:** `docs/deploy/P0-136-PR137-FE-RECOVERY-RELEASE.md` (not executed)

## Issue status (do not revoke)

| Issue | State |
|---|---|
| **#127** Fill / extended paper | **CLOSED** — owner Fill/save/refresh/reopen acceptance recorded; #136 is a **separate** post-deploy gate regression |
| **#128** POM persistence | **CLOSED** |
| **#135** Create My Croquis | **PAUSED** until #136 resolved |
| **#136** Studio gates / Restoring | **OPEN** |

## Phase A — compiled gates (unchanged findings)

| Gate | live `6ec73ba2` | rollback `ebcb1cc7` | known-good `69b83c01` |
|---|---|---|---|
| FRONT_BACK | OFF | OFF | ON |
| MAGIC_UI | OFF | OFF | ON |
| DUAL_MAGIC | OFF | OFF | ON |
| REGISTRATION | OFF | OFF | OFF |

Root cause: #134 clean build omitted Studio VITE env (no host `.env.production`; only API base + SHA). Restoring draft stuck = uncaught V2 serialize while Front/Back OFF.

## Phase B — rollback prepared, not preferred

`bash /var/www/fashionrise/releases/6ec73ba2/ROLLBACK.sh` → `ebcb1cc7` prepared. **Ineffective for gate restore** (ebcb also OFF). Prefer controlled forward recovery.

## Phase C — forward candidate requirements (PM P0/P1)

### P0-1 Compiled flag assertions (all four)

`scripts/assert-prod-vite-flags.mjs` now:

1. Requires **explicit Node `export VITE_*=…`** for the allowlist (documents that Vite may read gitignored `.env.production` into `import.meta.env` **without** populating `process.env` — env-only checks are insufficient alone).
2. Parses compiled `index-*.js` and fail-closed verifies **Front/Back, Dual Magic, Magic UI, Registration** helpers (`return!0` / `return!1`).
3. Writes `BUILD_ENV.txt` + `COMPILED_GATES.json` (booleans only).
4. Unit tests (`src/lib/assertProdViteFlags.test.ts`) flip **each** gate independently and expect failure.

Allowlist (from known-good `BUILD_ENV`, not example invention):

```
VITE_API_BASE_URL=/api/v1
VITE_REGISTRATION_UI_ENABLED=false
VITE_MAGIC_UI_ENABLED=true
VITE_STUDIO_FRONT_BACK_ENABLED=true
VITE_STUDIO_DUAL_MAGIC_ENABLED=true
```

### P0-2 New immutable release identity

**Do not** rebuild/overwrite `/var/www/fashionrise/releases/6ec73ba2` or reuse App pill `6ec73ba2` for different bytes.

When owner/PM authorizes deploy:

1. Checkout **final reviewed PR #137 tip** (contains restore-boot harden + assert).
2. `VITE_BUILD_SHA=<that tip full SHA>` matching the checkout.
3. Create **new unique** release dir e.g. `/var/www/fashionrise/releases/<shortsha>/`.
4. Verify nonempty assets + `BUILD_ENV.txt` + `COMPILED_GATES.json` (all four gates correct) **before** `ln -sfn`.
5. Preserve `6ec73ba2` and `ebcb1cc7` artifacts (both have gates OFF — document as non-restorative for Studio UI).
6. Leave API/worker `6cc317ec`, Alembic `011` untouched.

### P1-3 V2 no-overwrite regressions

`useStudioEditor.restoreBoot.test.tsx`:

- V2 draft with Back artwork retained (`hasBackInk`)
- Exits Restoring → `local-only` with actionable `studioNotice` (Front/Back · not overwritten)
- `persistStudioDraft` never called after serialize block or after `retrySave`
- Generic restore rejection → `error` / `Save failed` + not-overwritten notice; no cloud write
- V2 downgrade refusal preserved in `draftDocument.v2.test.ts`

## Verification (this tip)

| Check | Result |
|---|---|
| Focused assert + restore boot | green |
| Full Vitest | **675 passed / 6 known baseline fails** (disclose; unchanged historical set) |
| `tsc` / lint / prod build `/api/v1` + Access-safe SW + assert-prod-vite-flags | **PASS** (with explicit VITE exports; refuses `6ec73ba2*` BUILD_SHA) |
| Production activate | **NOT done** |

## Recommendation

Authorize FE-only deploy of **PR #137 tip** as a **new** release id with explicit VITE allowlist + compiled-gate verification before symlink. #135 remains PAUSED.
