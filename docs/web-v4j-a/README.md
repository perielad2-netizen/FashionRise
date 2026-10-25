# WEB-V4J-A — Front/Back croquis architecture pack

**Phase:** Architecture + reference matching only (Issue [#42](https://github.com/perielad2-netizen/FashionRise/issues/42)).  
**Paid AI:** **0**. **Production assets:** untouched. **No merge/deploy** in this pack.  
**Status (2026-10-25):** WEB-V4J **resumed**. P1 blockers [#51](https://github.com/perielad2-netizen/FashionRise/issues/51), [#59](https://github.com/perielad2-netizen/FashionRise/issues/59), [#60](https://github.com/perielad2-netizen/FashionRise/issues/60), [#64](https://github.com/perielad2-netizen/FashionRise/issues/64), and pose Issue [#39](https://github.com/perielad2-netizen/FashionRise/issues/39) are **CLOSED** (operator-accepted). This clean branch replaces the docs content of draft PR [#50](https://github.com/perielad2-netizen/FashionRise/pull/50) without inheriting that PR’s binary-bearing commit ancestry. **Keep PR #50 open** until Technical PM accepts this replacement.

## Contents

| Path | Purpose |
|------|---------|
| `front-ref-match-report.json` | Non-sensitive matching manifest: dimensions, transparency, content bbox, SHA-256 of private masters + shipped library files, IoU |
| `REAR-VIEW-ARTWORK-SPECS.md` | Per-model rear artwork brief (no flip/mirror) |
| `COMPATIBILITY-TEST-MATRIX.md` | Old/new client × draft/saved × offline/conflict checklist |
| `../WEB-V4J-A-FRONT-BACK-ARCHITECTURE.md` | Persistence strategy: **draft.v2 / saved_design.v2**, server reject-on-downgrade, BE fingerprint requirements |

## Public repository / asset provenance

This GitHub repo is **PUBLIC**. Operator-supplied front master PNGs were used for offline ID matching but **lack recorded redistribution rights** for publication.

**Clean-pack policy:** binary masters are **not** committed under `front-refs/`. Only the manifest + docs remain. Masters stay operator-held for any future ChatGPT briefing until rights are confirmed. Do not claim commercial clearance. No generated backs are approved.

**Public-history note:** PR #50 tip (`34e6d0d1`) no longer lists `front-refs/` in the tree, but commit `165865d8` on that branch still introduced the ten front-master PNGs. This replacement branch is cut from current `main` and does **not** reuse that ancestry. Old public commits may remain externally reachable; this pack does not rewrite GitHub history.

## Matching method

Uploads were **not** assumed to follow library order. Each PNG was matched to `/models/library/<id>.png` by content silhouette IoU + perceptual hash after alpha crop. All ten selectable built-ins received a unique assignment with IoU ≥ 0.98 (Cursor-reported). Exact original front model IDs are preserved; each still needs a genuine anatomically appropriate rear companion (not a mirrored front).

## Implementation sequence (ordered)

| Stage | Scope | Gate |
|-------|--------|------|
| **A — Architecture approval** | This clean docs PR | Technical PM review/accept; then close or supersede PR #50 |
| **B — Backend persistence safety** | `draft.v2` / `saved_design.v2` fingerprint, reject-on-downgrade, OCC, idempotency | Separate BE PR on **production maintenance lineage** (not blind `main` / undeployed PR #41 runtime) |
| **C — Rear croquis artwork** | Ten companion `-back.png` from accepted briefs + authorized fronts | Operator per-model or contact-sheet approval; provenance cleared before any commit |
| **D — Front/Back Studio UI** | Side switch, independent ink, save/reopen, undo, tablet, active-side export | Only after Stages B + C |

## Exact next actions after Stage A

1. Technical PM accept this architecture baseline.  
2. Authorize Stage B BE work against the deployed maint tip (currently `12f7acdf…`), with tests covering absent vs empty back, downgrade rejection, and back-only fingerprint changes.  
3. In parallel or after B: Stage C artwork from operator-held masters — **no shippable binaries** until approval.  
4. Stage D FE only after B is deployed and C assets are approved.
