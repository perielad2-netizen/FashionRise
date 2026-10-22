# WEB-V4D — Studio UX + Model Library QA notes

**Branch:** `cursor/web-v4d-studio-ux-77c6`  
**Scope:** Frontend-only. No backend, migration, Nginx, worker, or paid AI.

## What changed

1. **Model library refresh** — 10 approved croquis (6 female / 4 male) installed under `web-ui/public/models/library/` with card thumbs under `web-ui/public/assets/ui/models/library/`. Mapping: `web-ui/src/assets/MODEL_LIBRARY.md`.
2. **Defaults** — Female standing (`female`) and male standing (`male`) remain the selectable IDs for the straight defaults so existing drafts keep working.
3. **Unavailable placeholders removed** — no disabled “Unavailable” cards.
4. **Tabbed materials** — Colors / Fabrics / Gradients as compact tabs; gradients get a 2-column layout with more room.
5. **Focus mode** — Expand canvas control; hides models/settings/materials; quick access + Esc to exit.

## Acceptance checklist

| Check | Expected |
|-------|----------|
| Open Studio | Female standing croquis on cream paper with transparent bg |
| Male filter → Standing | Male standing croquis |
| Extra poses selectable | Hand on hip / Contrapposto / etc. render cleanly |
| No Unavailable cards | Only real models + Custom + Blank |
| Materials tabs | Switch Colors ↔ Fabrics ↔ Gradients without cramped cut-off |
| Fill solid / gradient / fabric | Still work after tab switch |
| Focus mode | Noticeably larger paper; can open Models/Materials overlays; Exit/Esc restores layout |
| Save / reopen / export | Unchanged paths still work |
| Magic button | Still present (gated by env); no paid call in this PR |

## Verification run

- `npm test` → **272 passed**
- `npm run lint` → pass (warnings only)
- `npm run build` + `npm run check:sw` → **ok=true**
- Backend changes: **none**

## Intentionally deferred

- Browser Fullscreen API (product focus mode is enough)
- Trimming library to exactly 4+4 (all 10 approved assets shipped)
- Production frontend deploy
- Paid Magic acceptance
