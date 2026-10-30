# P0 #136 — Studio gates missing after FE `6ec73ba2` deploy

**Status:** **CLOSED** — owner acceptance PASS on live FE `2dfcaba0` (2026-10-30)  
**Paid AI:** 0 · **BE/worker:** untouched `6cc317ec` · Alembic `011`  
**Branch / PR:** `cursor/web-incident-136-vite-flags-77c6` · PR [#137](https://github.com/perielad2-netizen/FashionRise/pull/137) (deployed, **not merged**)  
**Live FE:** `/var/www/fashionrise/releases/2dfcaba0` · source `2dfcaba0a97059adddceaa3ae8e0bee000fb32df`  
**Release runbook:** `docs/deploy/P0-136-PR137-FE-RECOVERY-RELEASE.md` (**executed**)  
**Backup:** `/var/backups/fashionrise/pr137-fe-recovery-deploy-20261030T122721Z/`

## Issue status (do not revoke)

| Issue | State |
|---|---|
| **#127** Fill / extended paper | **CLOSED** — owner acceptance; do not reopen for #136 |
| **#128** POM persistence | **CLOSED** |
| **#136** Studio gates / Restoring | **CLOSED** — owner six-point acceptance on `2dfcaba0` |
| **#135** Create My Croquis | **DESIGN · Stage A HOLD** — PR #138 PM PARTIAL PASS corrections; see `docs/CREATE-MY-CROQUIS-V1-DESIGN.md` |

## Distinguish deployment report vs owner acceptance

| Kind | What | Evidence |
|---|---|---|
| **Deployment (operator)** | Immutable FE release `2dfcaba0`, compiled gates ON, BE unchanged, 0 paid AI | [PR #137 deploy comment](https://github.com/perielad2-netizen/FashionRise/pull/137#issuecomment-6522888175) |
| **Acceptance (owner)** | Front/Back visible; Magic not Soon (not invoked); Restoring exits; V2 Back preserved; oversized Fill; save/reopen | [PR #137 PM acceptance](https://github.com/perielad2-netizen/FashionRise/pull/137#issuecomment-6523155424) · issue #136 closed |

Do not treat the deploy comment alone as product acceptance, and do not treat acceptance as authorization to merge #137 or change backend.

## Root cause (accepted)

#134 clean build omitted Studio VITE env. Compiled Front/Back, Magic, Dual Magic **OFF** on live `6ec73ba2` **and** rollback `ebcb1cc7`. Restoring stuck = uncaught V2 serialize while Front/Back OFF.

## Final compiled gates

| Gate | live `2dfcaba0` | prior `6ec73ba2` | `ebcb1cc7` |
|---|---|---|---|
| FRONT_BACK | **ON** | OFF | OFF |
| MAGIC_UI | **ON** | OFF | OFF |
| DUAL_MAGIC | **ON** | OFF | OFF |
| REGISTRATION | OFF | OFF | OFF |

## Recovery deploy (owner-authorized) — executed

| Item | Result |
|---|---|
| Source | Exact `2dfcaba0a97059adddceaa3ae8e0bee000fb32df` |
| Release | **new** `/var/www/fashionrise/releases/2dfcaba0` (never reused `6ec73ba2`) |
| Assert | `BUILD_ENV.txt` + `COMPILED_GATES.json` |
| Activate | Atomic `current` → `2dfcaba0` |
| BE/worker | Unchanged `6cc317ec` |
| Paid AI | **0** |
| Old dirs | `6ec73ba2`, `ebcb1cc7` intact (gates OFF) |

## Rollback note

`bash /var/www/fashionrise/releases/2dfcaba0/ROLLBACK.sh` → `6ec73ba2` restores prior FE only; **Studio gates remain OFF** on that artifact. Not recommended after acceptance of `2dfcaba0`.
