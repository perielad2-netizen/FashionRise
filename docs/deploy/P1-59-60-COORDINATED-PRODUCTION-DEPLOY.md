# FashionRise — Coordinated P1 #59 + #60 production deploy

**Result:** **SUCCESS**  
**Operator authorization:** [Issue #59 comment](https://github.com/perielad2-netizen/FashionRise/issues/59#issuecomment-6395058254)  
**Technical PM reviews:** [PR #61](https://github.com/perielad2-netizen/FashionRise/pull/61#issuecomment-6394847380) · [PR #62](https://github.com/perielad2-netizen/FashionRise/pull/62#issuecomment-6395000946)  
**Window (UTC):** 2026-10-25T08:16Z → 2026-10-25T08:30Z  
**Paid OpenAI / AI jobs created for testing:** **0**

Issues [#59](https://github.com/perielad2-netizen/FashionRise/issues/59) and [#60](https://github.com/perielad2-netizen/FashionRise/issues/60) remain **OPEN** pending operator acceptance.

## Exact source pins (reverified)

| Artifact | SHA |
|---|---|
| GitHub `main` (not used for BE/worker) | `c6fc1eb8b7eac4a2387dadd3b3e1c858d75a3b83` |
| PR #61 Magic identity FE | `c30dbc93a311bd5578ce5bd3ed7ef4515b7c6e3c` |
| PR #62 Narrow Fill FE | `b1018b46a031f4133708fc4e898366f0894aab8c` |
| Maint BE tip deployed | `74537077d0eaffd82391879e50195ed8928fe412` |
| Maint runtime identity commit | `1450b5a1d0b472058b47247d9d74133c7abd9c72` |
| Pre-deploy production BE/worker | `b800e53d25dcdf2481f377470543b323798796a7` |
| Pre-deploy production FE | `c6fc1eb8b7eac4a2387dadd3b3e1c858d75a3b83` |

Maint tip ancestry: `b800e53d` → runtime `ba2e87ab` / docs pin `1450b5a1` → docs-only commits → `74537077`.  
Diff vs production baseline only: `reference_croquis.py`, `ai_service.py`, `sketch_openai.py`, identity tests, two deploy docs. **No** PR #41 pose packing, migrations, dependency or model changes.

## Preflight (read-only) — PASS

| Check | Result |
|---|---|
| FE Nginx root | `/var/www/fashionrise/releases/c6fc1eb8` · `REVISION=c6fc1eb8…` |
| BE/worker git HEAD | `b800e53d…` (detached) |
| Dirty tree | clean (ignored only: `.env`, `__pycache__`, `web-ui/node_modules`, `web-ui/dist`) |
| `fashionrise-api` / `fashionrise-ai-worker` | **active** · standalone worker |
| `/health` `/ready` | `ok` / `ready`+`database=ok` |
| Alembic | **`005`** |
| Non-terminal AI jobs | **0** (completed 26 / failed 3) |
| Image config | `gpt-image-2.5-sunburst` · `high` · `1024x1536` · chat `gpt-6-luna` |
| Pose-fidelity runtime | absent on pre-deploy BE |
| Disk | 78G free |
| Neighbor apps | `pickwise` / other `/var/www` sites present — untouched |

## Backup

`/root/fashionrise-backups/p1-59-60-coord-20261025T081941Z`  
(symlink: `/var/backups/fashionrise/p1-59-60-coord-20261025T081941Z`)

Contents: original state record, FE `c6fc1eb8` tree, BE source tree (no `.env` in tree copy), mode-600 `.env` secret copy, systemd units, nginx site copy, `be-b800e53d.bundle`, `ROLLBACK.sh` (`fe-orig` / `be-orig` / `fe-release` / `full`).

## Offline verification

### Backend maint `74537077`

- Path audit vs `b800e53d`: **PASS** (6 files; post-`1450b5a1` docs-only)
- Full pytest: **331 passed** (222 warnings; no paid OpenAI)
- Non-enqueue identity harness on VPS after deploy: selectable male/female parse + optional missing `reference_model_id` → **PASS**

### Frontend Release A (identity only) — source `c30dbc93`

- web-ui delta vs prod FE: only Magic identity files (`magicApi.ts`, `useStudioEditor.ts` + tests)
- Vitest **379** · tsc PASS · oxlint warnings only (pre-existing) · build PASS · `check:sw` **ok**
- Flags unchanged: `VITE_API_BASE_URL=/api/v1`, registration UI on, Magic UI on
- Bundle: `assets/index-wOCHwPxc.js` · contains `reference_model_id`

### Frontend Release B (identity + narrow fill)

- Base: Release A; applied **only** `floodFill.ts` + `floodFill.narrow.test.ts` from `b1018b46` (byte-identical to PR #62)
- Vitest **436** · targeted identity+fill **74** · tsc PASS · oxlint warnings only · build PASS · `check:sw` **ok**
- No Front/Back; Hand→Pencil fix retained from production lineage; package/lock unchanged
- Combined content SHA256: `a740a9b7660df0c67f91c353575d4e1d581df7235bde24408c77e7c06f33b1a1`
- Release id: **`a740a9b7`** · bundle `assets/index-DFAeD0tH.js` (larger than A; contains `reference_model_id`)

## Stage 1 — Backend / AI worker

1. Queue recheck: **0** non-terminal  
2. `git checkout --detach 74537077…` on `/opt/fashionrise/src`  
3. Restart **only** `fashionrise-api` + `fashionrise-ai-worker`  
4. Post-check: HEAD `74537077…` · both **active** · `/health` `ok` · `/ready` ready · Alembic **`005`** · Sunburst **high** · no pose packing runtime · queue still **0**

`.env` image keys unchanged. No pip/global package updates. No migration.

## Stage 2 — Frontend Release A

- Installed immutable `/var/www/fashionrise/releases/c30dbc93` (SHA256SUMS verified)
- Nginx `root` `c6fc1eb8` → `c30dbc93` (`nginx -t` + reload)
- API/worker PIDs **unchanged** through FE switches
- Checkpoint retained for rollback Case C

## Stage 3 — Frontend Release B

- Installed immutable `/var/www/fashionrise/releases/a740a9b7`
- Nginx `root` `c30dbc93` → **`a740a9b7`**
- Live `nginx -T` root confirms `a740a9b7`
- Manifest proves both PR #61 identity source and PR #62 fill source
- Workbox SW: no NavigationRoute / createHandlerBoundToURL / HTML precache
- Public unauthenticated origin still Cloudflare Access **302** (invariant)

## Final production revisions

| Layer | Revision |
|---|---|
| Frontend | **`a740a9b7`** — combined identity+fill · `/var/www/fashionrise/releases/a740a9b7` |
| FE Release A checkpoint | `c30dbc93` (retained) |
| FE original baseline | `c6fc1eb8` (retained) |
| Backend + AI worker | **`74537077…`** |
| Alembic | **`005`** |
| Image model | `gpt-image-2.5-sunburst` / `high` / `1024x1536` |
| AI jobs total | 29 (26 completed + 3 failed) — **unchanged**; **0** created during deploy |

## Rollback matrix (ready)

| Case | Action |
|---|---|
| A — BE fail before FE | `ROLLBACK.sh be-orig` → `b800e53d`; FE stays `c6fc1eb8` |
| B — Identity FE fail | `ROLLBACK.sh fe-orig` or `fe-release c6fc1eb8` |
| C — Combined Fill FE fail | `ROLLBACK.sh fe-release c30dbc93` (keep BE if healthy) |
| D — Overall | `ROLLBACK.sh full` |

Do **not** downgrade Sunburst to retired `gpt-image-1`. No DB rollback expected.

## Explicit non-actions

- No paid Magic generation / polish POST
- No PR merges (#57, #61, #62, #41, etc.)
- No GitHub `main` backend deploy
- No Nginx allowlist / Cloudflare / neighbor-app changes beyond FashionRise `root` atomic switch
- No untracked cleanup / `git clean`
- Issues #59 / #60 **not closed**

## Operator acceptance (required; may incur cost for Magic)

**#59 Magic identity**

- Selected male croquis remains male-presenting after Magic
- Selected female croquis remains female-presenting
- Pose / garment / professional illustration quality preserved

**#60 Narrow fill** (~177% zoom, real device)

- Narrow hourglass + strap fills
- Adjacent seam isolation
- Large dress/trouser save-reopen persistence
