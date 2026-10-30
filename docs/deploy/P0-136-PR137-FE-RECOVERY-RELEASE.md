# P0 #136 / PR #137 — FE recovery release runbook (NOT EXECUTED)

**Status:** Prepared for Technical PM + owner authorization only. **Do not run until authorized.**  
**Scope:** Frontend-only. No BE/worker restart, migration, paid AI, or draft mutation.

## Why not `6ec73ba2`

Live `/var/www/fashionrise/releases/6ec73ba2` was built from `6ec73ba26ee5b8c25b29a77d31050942af4c6c6d` **without** Studio VITE gates and **without** PR #137 restore-boot / assert scripts. Rebuilding under that identity would claim false provenance.

Rollback target `ebcb1cc7` also has compiled Front/Back+Magic **OFF** — not a Studio UI fix.

## Source identity (update after final tip)

| Field | Value |
|---|---|
| Branch | `cursor/web-incident-136-vite-flags-77c6` |
| PR | [#137](https://github.com/perielad2-netizen/FashionRise/pull/137) |
| **Release source SHA** | `2dfcaba0a97059adddceaa3ae8e0bee000fb32df` (PR #137 Corrections A/B/C tip; not `6ec73ba2…`) |
| App / release dir | `/var/www/fashionrise/releases/2dfcaba0/` matching that tip |
| `VITE_BUILD_SHA` | `2dfcaba0a97059adddceaa3ae8e0bee000fb32df` (assert refuses empty or `6ec73ba2*`) |
| Must include | restore-boot harden + `assert-prod-vite-flags` all-four compiled gates + `/api/v1` |

## Required build exports

```bash
export VITE_API_BASE_URL=/api/v1
export VITE_REGISTRATION_UI_ENABLED=false
export VITE_MAGIC_UI_ENABLED=true
export VITE_STUDIO_FRONT_BACK_ENABLED=true
export VITE_STUDIO_DUAL_MAGIC_ENABLED=true
export VITE_BUILD_SHA=<FULL_PR137_TIP_SHA>
# Do not rely on gitignored .env.production alone — Node assert requires these exports.
cd web-ui && npm run build
# npm run build runs: tsc, vite, assert-sw-access-safe, assert-prod-api-base, assert-prod-vite-flags
```

`assert-prod-vite-flags` fail-closed checks **compiled** FRONT_BACK/MAGIC/DUAL/REGISTRATION + `/api/v1`, writes `dist/BUILD_ENV.txt` + `dist/COMPILED_GATES.json`.

## Immutable release procedure (after owner auth)

1. Checkout exact authorized tip; confirm `git rev-parse HEAD` equals authorized SHA.
2. Build with exports above.
3. Stage into **new** dir `/var/www/fashionrise/releases/<shortsha>/` — **never** overwrite `6ec73ba2` or `ebcb1cc7`.
4. Copy `BUILD_ENV.txt`, `COMPILED_GATES.json`, `version.json`, `REVISION`, `ROLLBACK.sh` → prior `6ec73ba2`.
5. **Before** symlink: nonempty `index.html`, `sw.js`, `assets/index-*.js`, `BUILD_ENV.txt`, `COMPILED_GATES.json` with all four gates correct + `apiBase=/api/v1`.
6. Atomic `ln -sfn …/<shortsha> …/current` · `nginx -t` · reload.
7. Smoke: App pill = shortsha · Front/Back visible · Magic not Soon · Restoring completes · **0 paid AI**.
8. Leave BE/worker `6cc317ec`, Alembic `011` untouched.

## Preserve

- Extended paper 1280×1536 from #134 lineage  
- V2 drafts / no browser storage clear / no V2→V1 downgrade  
- Old releases `6ec73ba2`, `ebcb1cc7` unchanged on disk  
