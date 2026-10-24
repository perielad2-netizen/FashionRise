# P1 #54 — Sunburst visual quality assessment (Technical PM requirement)

**Issue:** [#54](https://github.com/perielad2-netizen/FashionRise/issues/54)  
**Migration PR:** [#56](https://github.com/perielad2-netizen/FashionRise/pull/56)  
**Live call:** exactly **1** already-authorized isolated `images.edit` (no further paid A/B)  
**Saved operator Magic results:** used as **read-only** visual references — **not** modified or regenerated

## Release gate (PM)

Sunburst migration **must not** be treated as successful based on API compatibility, HTTP 200, or cost alone.  
Operator was highly satisfied with prior **GPT Image 1** Magic **professional fashion-illustration** style.

## Production prompt preservation (code)

On the migration branch, `_build_image_prompt` still requires:

- Professional fashion-design **illustration** finish (not pale wash / child-sketch retain)
- Preserve pose/stance, garment silhouette, colors, fabric/textile patterns, accessories
- Upgrade construction: folds, draping, texture, crisp patterns
- Explicit ban: **“Avoid photorealism, photography, CGI, magazine lookbook collage…”**

No additional paid call was used to re-probe prompt wording.

## Visual references (operator-approved / prior Magic — read-only)

| Reference | Style observed |
|-----------|----------------|
| Prior Magic look (browser static upload sample) | Stylized fashion croquis: elongated proportions, often faceless/minimal head, clean ink-like contours, soft flat-to-soft shading, **garment-forward illustration** |
| Prior Magic look (Unity “Your look” sample) | Same family: polished digital fashion sketch, dynamic pose, soft fabric draping, presentation illustration — **not** photoreal photography |

These files were inspected only. They were **not** edited, re-uploaded, or regenerated.

## One-shot Sunburst result (private harness)

| Dimension | Observation | Comparable to prior Magic? |
|-----------|-------------|----------------------------|
| API / transport | HTTP 200, 1024×1536 PNG returned | n/a (not a quality gate) |
| Pose (vs synthetic input) | Upright stance preserved; arms at sides | Partial — input was a stick croquis, not a designer sketch |
| Garment category / color | Navy swim shorts + white waistband retained | Yes for this simple garment |
| Textile / pattern complexity | Solid shorts only — **cannot** validate print/textile fidelity | **Insufficient evidence** |
| Fabric folds / polish | Soft shading on trunks present | Limited signal |
| **Illustration aesthetic** | Near-**photoreal / digital figure** rendering; facial detail; muscular realism | **No — significant gap** vs stylized illustration references |
| Photorealism ban | Harness used a **short non-production brief**, not `_build_image_prompt` | Harness result **violates** the spirit of the production “Avoid photorealism” rule |

### Significant visual differences (explicit)

1. **Style language:** Prior Magic = stylized fashion illustration. Sunburst harness = photoreal-leaning fashion figure.  
2. **Croquis abstraction:** Prior Magic often keeps fashion-proportion / simplified head language. Sunburst result reads as a rendered person.  
3. **Garment complexity:** Harness input lacked rich textiles/accessories → **cannot** certify color arrangement / textile pattern parity with production Magic.  
4. **Prompt path:** Live test did **not** exercise the production illustration prompt assembly — only provider model + edit endpoint compatibility.

## Quality verdict

| Gate | Result |
|------|--------|
| Provider integration | PASS (already recorded) |
| Cost within $1 auth | PASS (~$0.048) |
| **Visual quality vs operator-loved Magic** | **FAIL / insufficient for GO** |
| Production deploy readiness | **HOLD** |

**Automated observation** ≠ **operator approval.** Operator has not yet inspected the private Sunburst artifact for acceptance.

## Authorization boundary

- No additional paid A/B tests performed or requested.  
- No production deploy, merge, worker restart, or env mutation.  
- Production remains on retired `gpt-image-1` until a **separate** deploy authorization after quality acceptance.

## Exact next action for Technical PM / operator

1. Inspect the **private** Sunburst test image (local agent artifact; not in GitHub).  
2. Decide whether illustration language is acceptable **or** require production-prompt-path validation under a **new** paid authorization.  
3. Keep drafts #55 / #56 / #57 unmerged until quality gate clears.

## Production prompt parity (offline; after readiness)

See `docs/incidents/P1-54-PRODUCTION-PROMPT-PARITY.md`.

- Maintenance PR #57 `_build_image_prompt` is **identical** to production `2cbc1ad0` — professional illustration PRESERVE/UPGRADE/Avoid-photorealism language is **not** regressed by the Sunburst model swap.
- Migration PR #56 (from `main`) adds pose_lock packing from undeployed PR #41; style anchors still present. **#41 is not in the production maintenance candidate.**
- The consumed one-shot used a **non-production** short harness brief → photoreal result does **not** prove production Magic aesthetic failure or success.
- Automated offline scenario suite: `backend/tests/test_production_prompt_parity.py` (mocked; 0 paid calls).
- **Operator visual acceptance of the private one-shot image: still PENDING.** No claim of Magic recovery complete.

