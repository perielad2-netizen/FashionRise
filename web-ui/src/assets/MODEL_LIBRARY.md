# Built-in model library (WEB-V4D)

Approved croquis PNGs live under `public/models/library/` (canvas) and
`public/assets/ui/models/library/` (cards).

## Selectable picker models (new drawings)

| Model ID | Gender | Label | Default | Canvas | Card |
|---|---|---|---|---|---|
| `female-straight` | female | Standing | **yes** | `/models/library/female-straight.png` | `…/female-straight_card.png` |
| `female-hand-hip` | female | Hand on hip | | `/models/library/female-hand-hip.png` | `…/female-hand-hip_card.png` |
| `female-contrapposto` | female | Contrapposto | | `/models/library/female-contrapposto.png` | `…/female-contrapposto_card.png` |
| `female-cross-ankle` | female | Crossed ankles | | `/models/library/female-cross-ankle.png` | `…/female-cross-ankle_card.png` |
| `female-atelier` | female | Atelier | | `/models/library/female-atelier.png` | `…/female-atelier_card.png` |
| `female-cross-leg` | female | Crossed leg | | `/models/library/female-cross-leg.png` | `…/female-cross-leg_card.png` |
| `male-straight` | male | Standing | **yes** | `/models/library/male-straight.png` | `…/male-straight_card.png` |
| `male-step` | male | Step | | `/models/library/male-step.png` | `…/male-step_card.png` |
| `male-walk` | male | Walk | | `/models/library/male-walk.png` | `…/male-walk_card.png` |
| `male-contrapposto` | male | Contrapposto | | `/models/library/male-contrapposto.png` | `…/male-contrapposto_card.png` |

New empty drafts default to `female-straight`.

## Legacy IDs (not shown in picker)

| Model ID | Canvas (unchanged geometry) | Purpose |
|---|---|---|
| `female` | `/models/female_model.png` | Pre-V4D drafts / saved designs |
| `male` | `/models/male_model_display.png` | Pre-V4D drafts / saved designs |

These IDs are still valid `ModelChoice` values. Reopen, preview, export, and Magic
capture must resolve them to the **original** croquis files so strokes/fills stay
aligned. They are never rewritten to `*-straight`.

Custom and Blank utility cards are unchanged.
