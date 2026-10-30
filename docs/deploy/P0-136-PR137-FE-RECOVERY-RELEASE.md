# P0 #136 / PR #137 — FE recovery release runbook — EXECUTED

**Status:** **EXECUTED** 2026-10-30 after Technical PM ENGINEERING ACCEPTED + **owner authorization**.  
**Scope:** Frontend-only. No BE/worker restart, migration, paid AI, or draft mutation.

## Live result

| Field | Value |
|---|---|
| Branch | `cursor/web-incident-136-vite-flags-77c6` |
| PR | [#137](https://github.com/perielad2-netizen/FashionRise/pull/137) |
| **Release source SHA** | `2dfcaba0a97059adddceaa3ae8e0bee000fb32df` |
| App / release dir | `/var/www/fashionrise/releases/2dfcaba0/` |
| `current` | → `releases/2dfcaba0` |
| `VITE_BUILD_SHA` | `2dfcaba0a97059adddceaa3ae8e0bee000fb32df` |
| Compiled gates | FRONT_BACK=true · MAGIC_UI=true · DUAL_MAGIC=true · REGISTRATION=false · API=/api/v1 |
| BE / worker | **unchanged** `6cc317ecd55423403b6479e8bb185c3e4cde2bf1` |
| Alembic | **011** |
| Backup | `/var/backups/fashionrise/pr137-fe-recovery-deploy-20261030T122721Z/` |
| Rollback | `releases/2dfcaba0/ROLLBACK.sh` → `6ec73ba2` (**gates still OFF**) |
| Paid AI | **0** |
| Old releases | `6ec73ba2`, `ebcb1cc7` **unchanged** on disk |

## Why not `6ec73ba2`

Live `/var/www/fashionrise/releases/6ec73ba2` was built from `6ec73ba26ee5b8c25b29a77d31050942af4c6c6d` **without** Studio VITE gates and **without** PR #137 restore-boot / assert scripts. Rebuilding under that identity would claim false provenance. Recovery used a **new** immutable release id `2dfcaba0`.

Rollback target `ebcb1cc7` also has compiled Front/Back+Magic **OFF** — not a Studio UI fix.

## Build exports used

```bash
export VITE_API_BASE_URL=/api/v1
export VITE_REGISTRATION_UI_ENABLED=false
export VITE_MAGIC_UI_ENABLED=true
export VITE_STUDIO_FRONT_BACK_ENABLED=true
export VITE_STUDIO_DUAL_MAGIC_ENABLED=true
export VITE_BUILD_SHA=2dfcaba0a97059adddceaa3ae8e0bee000fb32df
cd web-ui && npm run build
```

`assert-prod-vite-flags` PASS · `BUILD_ENV.txt` + `COMPILED_GATES.json` written · Access-safe SW · `/api/v1`.

## Procedure completed

1. Checkout exact `2dfcaba0a97059adddceaa3ae8e0bee000fb32df`.
2. Build with exports above.
3. Staged **new** dir `/var/www/fashionrise/releases/2dfcaba0/` — did **not** overwrite `6ec73ba2` or `ebcb1cc7`.
4. Wrote `BUILD_ENV.txt`, `COMPILED_GATES.json`, `version.json`, `REVISION`, `RELEASE_NOTE.json`, `ROLLBACK.sh`.
5. **Before** symlink: verified nonempty `index.html`, `sw.js`, `assets/index-*.js`, gates, API base.
6. Atomic `ln -sfn …/2dfcaba0 …/current` · `nginx -t` · reload.
7. Operator smoke: App title `FashionRise · App 2dfcaba0` · live compiled helpers match allowlist · health/ready OK · BE unchanged · **0 paid AI**.
8. Owner Access-session UI acceptance still required for #136 close.

## Preserve

- Extended paper 1280×1536 from #134 lineage  
- V2 drafts / no browser storage clear / no V2→V1 downgrade  
- Old releases `6ec73ba2`, `ebcb1cc7` unchanged on disk  
