# WEB-V4D — Studio UX + Model Library QA notes

**Branch:** `cursor/web-v4d-studio-ux-77c6`  
**Scope:** Frontend-only. No backend, migration, Nginx, worker, or paid AI.

## What changed

1. **Model library refresh** — 10 approved croquis (6 female / 4 male) under `web-ui/public/models/library/` (+ cards). Mapping: `web-ui/src/assets/MODEL_LIBRARY.md`.
2. **Defaults** — New drawings use `female-straight` / `male-straight`.
3. **Legacy compatibility** — Stored `female` / `male` still resolve to `/models/female_model.png` and `/models/male_model_display.png` (original geometry). Not shown in the new picker. No stroke/fill remapping.
4. **Unavailable placeholders removed** — no disabled “Unavailable” cards.
5. **Tabbed materials** — Colors / Fabrics / Gradients as compact tabs; gradients get a 2-column layout with more room.
6. **Focus mode** — Expand canvas control; hides models/settings/materials; quick access + Esc to exit.

## Acceptance checklist

| Check | Expected |
|-------|----------|
| Open Studio | New default = `female-straight` croquis on cream paper |
| Male filter → Standing | `male-straight` croquis |
| Reopen old `model: female` design | Original `/models/female_model.png` geometry; strokes/fills unchanged |
| Extra poses selectable | Hand on hip / Contrapposto / etc. render cleanly |
| No Unavailable cards | Only real models + Custom + Blank |
| Materials tabs | Switch Colors ↔ Fabrics ↔ Gradients without cramped cut-off |
| Fill solid / gradient / fabric | Still work after tab switch |
| Focus mode | Noticeably larger paper; can open Models/Materials overlays; Exit/Esc restores layout |
| Save / reopen / export | Unchanged paths still work |
| Magic button | Still present (gated by env); no paid call in this PR |

## Verification run

- `npm test` → **278 passed** (includes legacy model geometry regressions)
- `npm run lint` → pass (warnings only)
- `npm run build` + `npm run check:sw` → **ok=true**
- Backend changes: **none**
- First paid Magic quality: **FAILED** (tracked separately as WEB-V4E; not in this PR)

## Intentionally deferred

- Browser Fullscreen API (product focus mode is enough)
- Trimming library to exactly 4+4 (all 10 approved assets shipped)
- Production frontend deploy
- Paid Magic acceptance
