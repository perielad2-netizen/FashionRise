# P1 #54 — Production prompt parity audit (offline)

**Production BE SHA:** `2cbc1ad04e5bfc01d1d356c92398e26e3014afe9`  
**Migration tip (PR #56):** `cursor/magic-image-sunburst-54-77c6`  
**Maint tip (PR #57):** `cursor/magic-maint-2cbc1ad0-54-77c6`  
**Paid calls in this audit:** **0**

## Method

Compared `backend/app/services/sketch_openai.py` `_build_image_prompt` (and helpers) across:

1. Deployed production revision `2cbc1ad0`
2. Sunburst migration branch (from `main`)
3. Offline maintenance branch (from `2cbc1ad0`)

Reconstructed full edit briefs offline from mocked vision JSON for five representative FashionRise cases (dress+textile, asymmetric pose, swimwear two-piece, shorts+top, coat+accessories/texture). Automated checks: `backend/tests/test_production_prompt_parity.py`.

## Findings

| Comparison | Result |
|------------|--------|
| Production `2cbc1ad0` vs PR **#57** `_build_image_prompt` | **BYTE-IDENTICAL** (same function body hash) |
| Production vs PR **#56** | **Different packing** — #56 inherits `main` pose_lock / CRITICAL POSE packing (PR #41 era). Core illustration style strings remain: PRESERVE, UPGRADE, fabric folds/patterns, Avoid photorealism |
| Style-instruction regression for Sunburst model swap alone | **None** on the production-maintenance path (#57) |
| One-shot live harness prompt | **Not** `_build_image_prompt` — short non-production brief; **not representative** |

## Style requirements still effective (prod / #57)

Offline assembly retains:

- Professional fashion-design **illustration** lead
- PRESERVE garment / pose / colors / textile patterns / accessories
- UPGRADE construction (folds, draping, texture, crisp patterns)
- Bans on pale wash / inventing a new garment
- **Avoid photorealism, photography, CGI…**

No speculative artistic retune was applied because of the photoreal harness result (per PM: do not modify the established Magic illustration prompt for that reason).

## Pre-existing production note (not introduced by Sunburst)

Production / #57 still use a hard `[:3800]` slice on the assembled prompt. Pathological verbose vision text can truncate the trailing avoid-line (confirmed offline on production/maint). Migration/`main` packing reserves the avoid-line first (pose-fidelity era). **PR #41 packing is not ported into #57.**

## Pose-fidelity PR #41

**Not** included in #57. Production Magic illustration language for a maintenance deploy is the **same** language operators already accepted with GPT Image 1.

## Conclusion

- **Prompt parity for the production maintenance candidate: PASS**
- **Representative Magic quality via paid Sunburst + full production prompt: NOT YET MEASURED** (auth consumed; harness was non-representative)
- **Operator visual acceptance: PENDING**
