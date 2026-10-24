# P1 #54 — One-shot live GPT Image 2.5 Sunburst validation

**Issue:** [#54](https://github.com/perielad2-netizen/FashionRise/issues/54)  
**Operator authorization:** [comment 6390781248](https://github.com/perielad2-netizen/FashionRise/issues/54#issuecomment-6390781248)  
**When (UTC):** 2026-10-24T23:25:51Z · **Asia/Jerusalem:** 2026-10-25 01:25 IDT  
**Harness:** isolated `/tmp` script — **not** production app, **not** committed image output  
**Paid calls this validation:** exactly **1** × `images.edit` · chat/vision **0** · generate **0** · retries **0**

## Request (fixed)

| Field | Value |
|-------|-------|
| Model | `gpt-image-2.5-sunburst` |
| Operation | `images.edit` |
| Quality | `high` |
| Size | `1024x1536` |
| `n` | `1` |
| `output_format` | `png` |
| SDK `max_retries` | `0` |
| `input_fidelity` | **omit** |
| Input | Synthetic offline croquis (ordinary navy swim shorts). **Not** customer art. **Not** the three failed production payloads. |

## Cost preflight (before call)

Official rates (Standard): text input $5/1M · image input $8/1M · image output $30/1M.  
Planning band **~$0.20–$0.80** (legacy high-portrait ~6240 output tokens ≈ $0.19 plus inputs; Sunburst may differ). Cap **$1**. **Proceeded.**

## Outcome: **SUCCESS** (API / provider integration)

| Field | Value |
|-------|--------|
| HTTP | **200** |
| Request id | `req_d436e6d92b76495eb09f2970860781b1` |
| Image present | **yes** |
| Dimensions | **1024×1536** |
| Latency | **23013 ms** |
| Usage | input 937 (text 73 + image 864) · output 1372 · total 2309 |
| Estimated cost | **~$0.048** (from usage × published rates) |
| Provider error | none |

Generated test image kept **private** under local `/tmp` (mode 600). **Not** uploaded to GitHub or production storage.

## Quality assessment (preliminary — not production Magic)

Operator-approved prior Magic looks are **stylized fashion illustrations** (clean outline, elongated croquis proportions, garment-forward polish).

This one-shot used a **synthetic stick-figure croquis** + a **short harness brief**, not the production `sketch_polish` prompt path or a real designer sketch. Returned image:

- Preserved upright pose and navy shorts with white waistband stripe.
- Rendered as a **polished, near-photoreal fashion figure / template**, not the same stylized illustration language as prior GPT Image 1 Magic samples.
- **Significant style gap vs operator-loved Magic illustration look** under these harness conditions.

**API compatibility alone must not green-light production.** No additional paid A/B authorized.

## What this does **not** prove

- Full FashionRise Magic pipeline (chat → structured JSON → production edit brief).
- Production pose / textile / garment fidelity on real user sketches.
- Safety of deploying undeployed PR #41.

## Production state (unchanged)

| Layer | Value |
|-------|--------|
| GitHub `main` | `c6fc1eb8b7eac4a2387dadd3b3e1c858d75a3b83` |
| Production FE | `c6fc1eb8` |
| Production BE/worker | `2cbc1ad04e5bfc01d1d356c92398e26e3014afe9` |
| Alembic | `005` |
| Worker image model | still `gpt-image-1` (retired) |
| Merges / deploys this task | **none** |

## Related PR heads (reverified)

| PR | Role | Head |
|----|------|------|
| [#55](https://github.com/perielad2-netizen/FashionRise/pull/55) | Observability (draft) | `9b86aca88faf4707f537524b064ad07bfae3182c` |
| [#56](https://github.com/perielad2-netizen/FashionRise/pull/56) | Sunburst migration (draft) | `d14f401662142461a25fa75eef5f2402a8c3e7b8` |
| [#57](https://github.com/perielad2-netizen/FashionRise/pull/57) | Offline maint off `2cbc1ad0` (draft, not for deploy) | `40f4d2fda201544a8bc969f99e99a107122812d5` |

## Exact next release action (PM)

1. Human visual review of private Sunburst result vs prior Magic illustration quality.  
2. If illustration language must match GPT Image 1 Magic more closely: adjust **production** edit brief on the migration/maint branches **offline**, then seek **separate** authorization for any further paid check.  
3. Only after quality acceptance: authorize **maintenance deploy** of PR #57 candidate (or equivalent) + env `OPENAI_IMAGE_MODEL=gpt-image-2.5-sunburst` / `OPENAI_IMAGE_QUALITY=high`.  
4. **Do not** merge #55/#56/#57 from this report alone. **Do not** deploy full `main` BE (excludes #41 pose from prod).
