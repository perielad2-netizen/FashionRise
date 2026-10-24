# WEB-V4J-A — Front/Back croquis architecture pack

**Phase:** Architecture + reference matching only (Issue [#42](https://github.com/perielad2-netizen/FashionRise/issues/42)).  
**Paid AI:** **0**. **Production assets:** untouched. **No merge/deploy** in this pack.  
**Priority:** Implementation and rear art generation are **PAUSED** until P1 Issue [#51](https://github.com/perielad2-netizen/FashionRise/issues/51) ships.

## Contents

| Path | Purpose |
|------|---------|
| `front-ref-match-report.json` | Non-sensitive matching manifest: dimensions, transparency, content bbox, SHA-256 of private masters + shipped library files, IoU |
| `REAR-VIEW-ARTWORK-SPECS.md` | Per-model rear artwork brief (no flip/mirror) |
| `COMPATIBILITY-TEST-MATRIX.md` | Old/new client × draft/saved × offline/conflict checklist |
| `../WEB-V4J-A-FRONT-BACK-ARCHITECTURE.md` | Persistence strategy: **draft.v2 / saved_design.v2**, server reject-on-downgrade, BE fingerprint requirements |

## Public repository / asset provenance

This GitHub repo is **PUBLIC**. Operator-supplied front master PNGs were used for offline ID matching but **lack recorded redistribution rights** for publication.

**Amended pack policy:** binary masters are **not** committed under `front-refs/`. Only the manifest + docs remain. Masters stay operator-held for any future ChatGPT briefing until rights are confirmed. Do not claim commercial clearance. No generated backs are approved.

## Matching method

Uploads were **not** assumed to follow library order. Each PNG was matched to `/models/library/<id>.png` by content silhouette IoU + perceptual hash after alpha crop. All ten selectable built-ins received a unique assignment with IoU ≥ 0.98 (Cursor-reported).

## Next gates (ordered)

1. **P1 #51** Hand→Pencil hotfix reviewed, merged, FE-deployed, operator-accepted.  
2. Technical PM re-review of this amended architecture (schema v2 + BE downgrade guards).  
3. Authorized **backend** fingerprint / reject-on-downgrade PR + tests.  
4. Operator-held masters → ChatGPT rear proposals → operator art acceptance.  
5. WEB-V4J-B FE: approved `-back.png`, dual-reader, Front/Back UI (only after BE guards).
