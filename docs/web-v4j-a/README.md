# WEB-V4J-A — Front/Back croquis architecture pack

**Phase:** Architecture + reference matching only (Issue [#42](https://github.com/perielad2-netizen/FashionRise/issues/42)).  
**Paid AI:** **0**. **Production assets:** untouched. **No merge/deploy** in this pack.

## Contents

| Path | Purpose |
|------|---------|
| `front-refs/<modelId>.front-ref.png` | Operator-supplied front masters, renamed after silhouette match to library IDs |
| `front-ref-match-report.json` | Dimensions, transparency, SHA-256, content bbox, shipped-library comparison |
| `REAR-VIEW-ARTWORK-SPECS.md` | Per-model rear artwork brief for ChatGPT image generation (no flip/mirror) |
| `../WEB-V4J-A-FRONT-BACK-ARCHITECTURE.md` | Persistence, compatibility, UI/export/Magic boundaries |

## Matching method

Uploads were **not** assumed to follow library order. Each PNG was matched to `/models/library/<id>.png` by content silhouette IoU + perceptual hash after alpha crop. All ten selectable built-ins received a unique assignment with IoU ≥ 0.98.

## Next gates

1. Technical PM review of architecture + specs (this PR).  
2. ChatGPT (or operator) produces proposed rear PNGs from the specs.  
3. Operator visual approval of rears.  
4. Separate implementation PR (WEB-V4J-B+) wires approved rears + side-aware document fields — only after approval.
