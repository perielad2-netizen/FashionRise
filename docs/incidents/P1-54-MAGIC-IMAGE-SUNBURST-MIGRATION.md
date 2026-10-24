# P1 #54 — Magic image model migration to GPT Image 2.5 Sunburst

**Issue:** [#54](https://github.com/perielad2-netizen/FashionRise/issues/54)  
**Companion observability PR:** [#55](https://github.com/perielad2-netizen/FashionRise/pull/55) (separate; not mixed here)  
**Paid OpenAI / production deploy this PR:** **0 / none**

## Why

Official OpenAI docs: **`gpt-image-1` shut down on 2026-10-23**. Production worker still has `OPENAI_IMAGE_MODEL=gpt-image-1`. Three Magic failures (chat 200 → images.edit 400) followed. Retirement is the leading explanation; historical provider codes were not logged.

Preferred replacement: **`gpt-image-2.5-sunburst`** (precision editing). Alternative later: `gpt-image-2.5-flare`.

## SDK / API compatibility evidence

| Item | Evidence |
|------|----------|
| Installed / required SDK | `openai>=1.109.1,<2.0.0` (repo floor; validated 1.109.1) |
| Model id typing | `ImageEditParams.model` is `Union[str, ImageModel, None]` — string ids including Sunburst are accepted even when typed `ImageModel` literal lags |
| Endpoint | Keep `client.with_options(max_retries=0).images.edit(...)` — no `images.generate` fallback |
| Docs | https://developers.openai.com/api/docs/models/gpt-image-2.5-sunburst · image generation guide · deprecations · python images.edit |

## Model capability table (code)

| Model | Status | `input_fidelity` | Qualities used | `output_format` | Sizes |
|-------|--------|------------------|----------------|-----------------|-------|
| `gpt-image-2.5-sunburst` | supported (default) | **omit** | `high` default; never silent `xhigh`/`max` | `png` | `1024x1536` preserved |
| `gpt-image-2.5-flare` | supported (optional) | **omit** | same guardrails | `png` | same |
| `gpt-image-2` | supported | **omit** (docs) | up to `high` | `png` | same |
| `gpt-image-1.5` | supported | may set `high` | up to `high` | `png` | same |
| `gpt-image-1` / `gpt-image-1-mini` | **retired** | n/a | n/a | n/a | **fail closed before HTTP** |

## Request shape (Sunburst)

- `model=gpt-image-2.5-sunburst`
- `image` = original sketch bytes (png/jpeg/webp)
- `prompt` = existing FashionRise edit brief (pose/garment protections unchanged)
- `size=1024x1536`
- `quality=high`
- `output_format=png`
- `n=1`
- **no** `input_fidelity`
- SDK `max_retries=0` for the edit call only
- No silent fallback to Flare / generate / mini

Vision/text model remains **`gpt-6-luna`**.

## Cost estimate (official rates; not authorization to spend)

Sunburst / Flare Images API token rates (Standard):

| Token class | Price |
|-------------|-------|
| Text input | $5 / 1M |
| Text cached input | $1.25 / 1M |
| Image input | $8 / 1M |
| Image output | $30 / 1M |

Notes:

- Direct `/v1/images/edits` does **not** use cached image-input pricing.
- Exact tokens for FashionRise sketch + `1024x1536` + `quality=high` **are not measured here** (no live probe). Older GPT Image high-portrait output was on the order of ~6k image output tokens (~$0.19 at $30/1M) **plus** image/text input — Sunburst token counts can differ; treat **~$0.20–$0.60 per successful edit** as a planning band until a later authorized single live measurement.
- Chat Completions (`gpt-6-luna`) costs remain separate per Magic job.
- Choosing `high` (not `xhigh`/`max`) is an intentional cost/quality tradeoff.

## Product behavior preserved

- Edit-only look path; original sketch preserved on failure.
- Legitimate swimwear/apparel not rejected by app validation/prompt construction (mocked fixtures).
- Pose-fidelity prompt tests on `main` remain green; **PR #41 is still not auto-deployed** by this PR alone.

## Production isolation (critical)

Do **not** deploy entire `main` BE/worker (contains undeployed pose-fidelity PR #41).

See `docs/incidents/P1-54-PRODUCTION-MAINTENANCE-ISOLATION.md` for the offline maintenance branch based on production SHA `2cbc1ad0`, combining only approved observability + this migration after PM authorization.

## Config

Code default + `.env.example`: `OPENAI_IMAGE_MODEL=gpt-image-2.5-sunburst`, `OPENAI_IMAGE_QUALITY=high`.  
**This PR does not modify production `.env`.**

## Exact next Technical PM action

Review this migration PR + isolation plan + observability PR #55. Later authorize a bounded maintenance release and optional single budgeted Magic validation on Sunburst. **No deploy from this task.**
