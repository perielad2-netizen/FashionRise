# WEB-V4J — PAIRS_09 rear croquis integration (PR #69)

**Status:** Installed on draft PR [#69](https://github.com/perielad2-netizen/FashionRise/pull/69). Awaiting Technical PM review. **Not deployed.** Production `VITE_STUDIO_FRONT_BACK_ENABLED` remains **OFF**.

## Source

Operator-approved ZIP pairs under `FashionRise_FrontBack_Sorted/PAIRS_09/<model-id>/{front,back}.png`.

ZIP `front.png` files were used only for measurement/comparison. **Shipped library Front masters were not replaced.**

## Installed Back assets

Public paths: `/models/library/<model-id>-back.png`

| Model ID | Back file | Canvas size (matches Front) | Published |
|---|---|---|---|
| female-straight | `female-straight-back.png` | 656×1199 | yes |
| female-hand-hip | `female-hand-hip-back.png` | 656×1199 | yes |
| female-contrapposto | `female-contrapposto-back.png` | 900×1200 | yes |
| female-cross-ankle | `female-cross-ankle-back.png` | 900×1200 | yes |
| female-cross-leg | `female-cross-leg-back.png` | 900×1200 | yes |
| male-straight | `male-straight-back.png` | 900×1200 | yes |
| male-step | `male-step-back.png` | 900×1200 | yes |
| male-walk | `male-walk-back.png` | 900×1200 | yes |
| male-contrapposto | `male-contrapposto-back.png` | 900×1200 | yes |
| female-atelier | — | — | **no** (no approved Back) |

## Alignment method

For each pair:

1. Measure figure bounding box on library Front and ZIP Back.
2. Convert ZIP Back near-black background to clean alpha.
3. Uniform (proportion-preserving) scale so Back figure height matches Front.
4. Translate so vertical center and head/foot landmarks match the Front canvas.
5. Reject if shoulder-width scale would need >18% deviation from height scale (would require distortion).

All nine pairs passed automated acceptance. Alignment contact + overlay sheets for PM review: agent artifacts `v4j-pairs09-align/`.

## Feature gates

- `REAR_CROQUIS_PUBLISHED`: nine IDs `true`; `female-atelier` `false`.
- `VITE_STUDIO_FRONT_BACK_ENABLED`: default **false** (production-safe).
- Flip Paper / Back UI requires **both** the env flag and a published rear asset.

## UX (PM product decision 2026-10-25)

- Models library shows **one Front thumbnail per model** — never a separate Back tile.
- Flip lives on the drawing paper (upper-right): rotate icon + FRONT/BACK label; tooltip “Flip to Back” / “Flip to Front”.
- Header/immersive toolbar no longer host the Front/Back segmented control.
- Unavailable Back (e.g. `female-atelier`) keeps the control but explains via tooltip + studio notice; does not open a blank Back.

## Out of scope this change

- No production deploy / feature activation
- No paid Magic calls
- No DB migration
- No PR #70 rework
- No `female-atelier` Back substitute
