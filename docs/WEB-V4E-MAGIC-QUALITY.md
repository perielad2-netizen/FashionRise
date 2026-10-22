# WEB-V4E — Magic quality (professional fashion refinement)

**Status:** Draft — **STOP for Technical PM review**. No merge / no deploy / no paid AI in this PR.  
**Branch:** `cursor/web-v4e-magic-quality-77c6` (based on `main` @ `c21fee6b`, **not** WEB-V4D).

## Operator outcome (production)

| Item | Result |
|------|--------|
| First paid Magic browser job | **Completed** |
| Technical pipeline | Worked (vision → edit → store → poll → authenticated image) |
| Quality acceptance | **FAILED** — too pale / not professional fashion polish |
| Desired outcome | Amateur sketch → beautiful professional fashion-design illustration; preserve creative intent |

Cursor agent paid OpenAI calls during this implementation: **0**.

## Root-cause investigation (code-supported)

Confirmed findings (not unverified guesses):

1. **Edit prompt bias toward pale cleanup** — `_build_image_prompt` previously instructed: “Only clean the linework and add a light color wash” and “Result must still look like the child's sketch”. That conflicts with professional fashion-illustration polish and matches the rejected pale look.
2. **Reference-less `images.generate` fallback** — if `images.edit` failed, the worker could call `images.generate` with the same text prompt and **no sketch pixels**, inventing a new image. That is not an equivalent design-preserving path.
3. **Vision brief was attribute-light** — polish system prompt asked for a short `image_prompt` of pose/hat/neckline/sleeves/hem/shapes, without structured design-identity vs drawing-imperfection separation.
4. **Unity vs React input is not identical** (same API, different capture):
   - Unity sketch pad composites onto a **white** reference buffer.
   - React Magic capture uses `exportSketchPng` with cream paper `#F8F4F0`, fills + ink, and dimmed reference underlay.
   - Do **not** assume identical model inputs merely because both POST `/ai/sketch/polish`.
5. **Models unchanged** — production text analysis remains `gpt-6-luna`; image edit remains `gpt-image-1` with `input_fidelity=high`. No model swap without evidence/authorization.

Hypotheses not proven without a new paid visual run:

- Cream paper vs white paper contribution to washiness.
- Fill layers vs ink-only capture contribution.
- Whether `input_fidelity=high` alone would have been enough without prompt changes.

## Changes in this PR

| Area | Change |
|------|--------|
| Vision system prompt (`sketch_polish`) | Design director brief; `design_identity` + `refine_ok`; richer `image_prompt` rules |
| `_build_image_prompt` | Professional fashion illustration + strict concept fidelity; removes light-wash / child-sketch retain language |
| Look pipeline | **Edit only** — no `images.generate` fallback; missing sketch or failed edit → `SketchCompletionError` |
| Provenance | `image_provenance: "images.edit"` when a look URL is stored |
| Models | **Unchanged** (`gpt-6-luna` / `gpt-image-1`) |

## Human visual acceptance rubric (post-deploy)

Automated prompt tests **do not** prove images look good. After authorized deploy, operator runs **one** controlled browser Magic job and scores:

| Criterion | Pass bar |
|-----------|----------|
| Design fidelity | Same garment category, silhouette, neckline, sleeves, hem, accessories (e.g. wide-brim hat), asymmetry |
| Professionalism | Looks like a talented fashion illustrator/designer presentation — not a faint wash on a kid sketch |
| Fabric/color fidelity | Main colors and textile patterns richer but recognizable |
| Silhouette/pose fidelity | Pose and body proportions match the source sketch |
| Visual attractiveness | Clean full-body fashion presentation; clear seams/hems/contours |

Operator sample must remain recognizable: wide-brimmed hat, deep V neckline, flowing sleeves, pink patterned jumpsuit, asymmetric leg design.

## Tests (offline)

`pytest backend/tests/test_magic_quality_prompts.py` (+ existing OpenAI migration suite). Coverage:

- Professional refinement + fidelity language
- Operator-sample attributes in edit prompt
- Edit request construction (`input_fidelity=high`, sketch bytes)
- No generate fallback / genuine failure
- Provenance + no base64/secret leaks in failure tokens

## Intentionally not done

- No paid OpenAI / Higgsfield calls
- No re-run of the operator’s production job
- No model changes
- No merge / deploy / Nginx / migrations
- No claim of visual acceptance
