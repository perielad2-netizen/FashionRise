# P0 #136 — Studio gates missing after FE `6ec73ba2` deploy

**Status:** FE recovery **DEPLOYED** as `2dfcaba0` (PR #137) · **#136 OPEN** pending owner UI acceptance · #135 PAUSED  
**Paid AI:** 0 · **BE/worker:** untouched `6cc317ec` · Alembic `011`  
**Branch:** `cursor/web-incident-136-vite-flags-77c6` · PR [#137](https://github.com/perielad2-netizen/FashionRise/pull/137)  
**Live FE:** `/var/www/fashionrise/releases/2dfcaba0` · source `2dfcaba0a97059adddceaa3ae8e0bee000fb32df`  
**Release runbook:** `docs/deploy/P0-136-PR137-FE-RECOVERY-RELEASE.md` (**executed**)  
**Backup:** `/var/backups/fashionrise/pr137-fe-recovery-deploy-20261030T122721Z/`

## Issue status (do not revoke)

| Issue | State |
|---|---|
| **#127** Fill / extended paper | **CLOSED** — owner Fill/save/refresh/reopen acceptance recorded; #136 is a **separate** post-deploy gate regression |
| **#128** POM persistence | **CLOSED** |
| **#135** Create My Croquis | **PAUSED** until #136 owner-accepted |
| **#136** Studio gates / Restoring | **OPEN** — recovery FE live; owner Access-session confirmation pending |

## Root cause (accepted)

#134 clean build omitted Studio VITE env (no host `.env.production`; only API base + SHA). Compiled Front/Back, Magic, Dual Magic **OFF** on live `6ec73ba2` **and** rollback `ebcb1cc7`. Restoring draft stuck = uncaught V2 serialize while Front/Back OFF.

## Pre-recovery compiled gates

| Gate | live `6ec73ba2` (pre) | rollback `ebcb1cc7` | known-good `69b83c01` | **live `2dfcaba0` (now)** |
|---|---|---|---|---|
| FRONT_BACK | OFF | OFF | ON | **ON** |
| MAGIC_UI | OFF | OFF | ON | **ON** |
| DUAL_MAGIC | OFF | OFF | ON | **ON** |
| REGISTRATION | OFF | OFF | OFF | **OFF** |

## Recovery deploy (owner-authorized)

| Item | Result |
|---|---|
| Source | Exact `2dfcaba0a97059adddceaa3ae8e0bee000fb32df` |
| Release | **new** `/var/www/fashionrise/releases/2dfcaba0` (never reused `6ec73ba2`) |
| Assert | `BUILD_ENV.txt` + `COMPILED_GATES.json` all four gates + `/api/v1` |
| Activate | Atomic `current` → `2dfcaba0` · nginx reload |
| BE/worker | Unchanged `6cc317ec` |
| Paid AI | **0** |
| Old dirs | `6ec73ba2`, `ebcb1cc7` intact (gates OFF — rollback is not a Studio UI fix) |

## Owner acceptance checklist (Access session)

1. Hard-refresh · App pill **`2dfcaba0`**
2. Front/Back switcher visible
3. Magic **not** “Soon” (do **not** start paid generation unless separately authorized)
4. Restoring draft exits to Saved / Ready / explicit safe notice — not stuck
5. Existing V2 Back artwork still present
6. Oversized Fill still works (#127 paper lineage)

## Rollback note

`bash /var/www/fashionrise/releases/2dfcaba0/ROLLBACK.sh` → `6ec73ba2`. Restores prior FE service only; **Studio gates remain OFF** on that artifact.
