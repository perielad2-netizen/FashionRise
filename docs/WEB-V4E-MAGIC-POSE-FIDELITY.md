# WEB-V4E maintenance — Magic pose fidelity (Issue #39)

**Status:** Draft PR — **STOP for Technical PM review**. No merge / no deploy / no worker restart / no paid AI.  
**Branch:** `cursor/magic-pose-fidelity-77c6` from `main` @ `1aa5dc5a` (WEB-V4F already on main).  
**Scope:** Backend Magic vision + edit-brief pose lock only. **Not** WEB-V4G (brushes/gradients).

## Operator report

| Item | Result |
|------|--------|
| Symptom | Magic professionally refinishes the sketch but **changes the model stance** |
| Original | Asymmetric dynamic croquis: one leg bent/angled away from supporting leg; body/hips follow the fashion pose; bent arm / hand-at-waist concept |
| Magic result | More conventional upright stance; **both boots lowered/planted**; still polished and keeps hat / pink outfit / sleeve / hem asymmetry concepts |
| Classification | AI product-fidelity bug (not CSS/mobile). WEB-V4E polish quality remains desired; pose preservation **not accepted** for this sample |
| Source images | Operator ChatGPT report (2026-10-23). Not hosted on the GitHub issue. Cursor workspace artifacts under `/opt/cursor/artifacts/pose-fidelity/` are croquis/UI references, **not** the operator’s pink sketch ↔ Magic pair |

Cursor agent paid OpenAI calls during this implementation: **0**.

## Investigation findings (code-supported)

1. **Pipeline unchanged in shape** — still vision JSON (`gpt-6-luna`) → one `images.edit` (`gpt-image-1`, `input_fidelity=high`, `max_retries=0`) with the original sketch bytes. No generate fallback, no secondary model.
2. **Root cause class** — generative edit + **weak pose brief**. Pre-fix `design_identity.pose` was free text and easily collapsed to generics such as `"standing front view"`, while the edit prompt only said “PRESERVE … pose” without concrete limb/weight relationships or explicit anti-repose bans.
3. **Instructions ≠ geometry** — `input_fidelity=high` and pose wording bias the edit model; they do **not** geometrically lock joints. Prompt improvements can reduce repose risk but cannot guarantee pixel-identical limb positions.
4. **Capture / salience (React)** — Magic uses `captureSketchForMagic` → `exportSketchPng` at **768×1024** cream paper `#F8F4F0`, fills + ink, reference underlay often at **opacity 0.4** when dimmed, fit-contain into the design space. That can soften croquis contour contrast relative to garment fill color. This PR does **not** change capture (no unverified resize/opacity experiment; would need authorized visual A/B).
5. **Masks / pose guidance** — optional future design investigation only. Masks alone are not proven to preserve both pose and WEB-V4E polish; out of scope here.

## Changes in this PR

| Area | Change |
|------|--------|
| Vision system prompt (`sketch_polish`) | Requires structured `design_identity.pose_lock` (torso, shoulders, hips, supporting leg, bent/lifted leg, knees, feet, arms/hands, asymmetry/perspective); forbids inventing anatomy; rejects generic “standing front view” summaries when limbs are dynamic |
| `_design_identity_clause` / `_pose_lock_clause` | Emits an explicit **POSE LOCK** block; skips generic free-text `pose` when `pose_lock` is present |
| `_build_image_prompt` | Keeps WEB-V4E professional polish language; adds CRITICAL POSE RULES; **priority-packs** pose_lock facts (supporting/bent leg, feet, knees, arms/hands, shoulder/hip) before garment fluff and free-text `image_prompt`; per-fact bounds; whole-segment budget — **no** `[:3800]` mid-fact truncation |
| Models / edit policy | **Unchanged** (`gpt-6-luna` / `gpt-image-1`, edit-only, high fidelity, one attempt, `max_retries=0`) |
| Auth / storage / recovery | Untouched |

## Human visual-acceptance rubric (post-authorize only)

Automated prompt tests **do not** assert image quality. After separate merge + deploy + **one** authorized paid operator Magic retest, score:

| Criterion | Pass bar |
|-----------|----------|
| Supporting vs free leg | Same supporting leg; bent/lifted/angled leg still bent/lifted/angled (not both boots planted if original was not) |
| Knees / hips / shoulders | Same relative knee bend; hip tilt and shoulder alignment match the source croquis relationships |
| Arms / hands | Hand-on-hip (or other arm positions) on the same side; no limb swap |
| Composition | Same full-body framing and croquis proportions |
| Garment / color / textile | Silhouette, accessories, color arrangement, textile pattern as faithful as the model permits |
| Professionalism | WEB-V4E-level polished fashion illustration — not a pale wash, not a pose rewrite |

**Final gate:** human operator only. Unit tests must never be marked as visual PASS.

## Expected limitations (honest)

- Prompt + high input fidelity **bias** preservation; they do **not** guarantee geometrically exact pose.
- If vision under-describes the stance, the edit brief cannot invent correct relationships.
- Dimmed 768×1024 capture may still reduce pose salience vs garment color fills.
- Checked→striped textile drift (earlier sample) is related fidelity risk; this PR strengthens textile language retention via existing identity fields but does not add a separate pattern-lock stage.
- If a post-deploy retest still reposes the figure, next options are design investigation (capture opacity/resolution A/B, optional mask/pose guidance research) — not speculative model swaps.

## Tests (offline)

```bash
cd backend && .venv/bin/pytest tests/test_magic_pose_fidelity_prompts.py tests/test_magic_quality_prompts.py -q
```

Coverage includes bent-leg, crossed-leg, hand-on-hip, asymmetric stance, checked textile language, generic-pose suppression, verbose vision truncation regression (critical pose tokens retained inside budget), and retention of WEB-V4E polish bans. **0 paid calls.**

## Intentionally not done

- No paid OpenAI / Magic generation
- No production deploy / worker restart / Nginx / migrations
- No WEB-V4G brush/gradient work
- No model changes
- No claim of visual acceptance from unit tests
