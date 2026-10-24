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

Exact model ids only, plus **documented** snapshot alias `gpt-image-2.5-sunburst-2026-09-08`.  
Arbitrary `gpt-image-2.5-sunburst-*` / `flare-*` / `gpt-image-2-*` prefixes are **rejected** (fail closed, 0 paid edits).

| Model | Status | `input_fidelity` | Qualities used | `output_format` | Sizes |
|-------|--------|------------------|----------------|-----------------|-------|
| `gpt-image-2.5-sunburst` | supported (default) | **omit** | `high` default; legacy `standard`→`high`; `xhigh`/`max`/unknown **fail closed** | `png` | `1024x1536` preserved |
| `gpt-image-2.5-flare` | supported (optional) | **omit** | same guardrails | `png` | same |
| `gpt-image-2` | supported | **omit** (docs) | up to `high` (FashionRise allowlist) | `png` | same |
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

Sunburst Images API token rates (Standard):

| Token class | Price |
|-------------|-------|
| Text input | $5 / 1M |
| Image input | $8 / 1M |
| Image output | $30 / 1M |

Notes:

- Official docs: GPT Image 2 calculator **does not** predict GPT Image 2.5 token consumption.
- Direct `/v1/images/edits` does **not** use cached image-input pricing.
- Third-party measured ~$0.05 for a short-prompt 1024×1536 high edit is **not** a FashionRise guarantee.
- Isolated one-shot (synthetic croquis, short harness brief): usage-based est. **~$0.048** — see `P1-54-LIVE-SUNBURST-VALIDATION.md`.
- Production Magic also incurs separate Chat Completions (`gpt-6-luna`) vision cost — **not** included in the image-edit figure.
- The operator $1 ceiling is a **planning** limit, not a provider-enforced cap.
- Choosing `high` (rejecting `xhigh`/`max` in config) is an intentional cost/quality tradeoff.

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

## One-shot live validation (authorized; completed)

Operator authorization: Issue #54 comment `6390781248`. Isolated harness (not production). Exactly **1** `images.edit`.

| Result | Detail |
|--------|--------|
| Outcome | **SUCCESS** (provider integration) |
| Model / params | `gpt-image-2.5-sunburst` · `high` · `1024x1536` · `n=1` · `png` · `max_retries=0` · no `input_fidelity` · no generate |
| HTTP / image | **200** · image present **1024×1536** · latency **23013 ms** |
| Usage / cost | input 937 (text 73 + image 864) · output 1372 · est. **~$0.048** (cap $1) |
| Quality | Preliminary **HOLD** vs prior stylized Magic illustration — see `P1-54-LIVE-SUNBURST-VALIDATION.md` |
| Production | **Unchanged** (FE `c6fc1eb8` · BE/worker `2cbc1ad0` · Alembic `005` · still `gpt-image-1`) |

## Exact next Technical PM action

1. Review private Sunburst visual vs operator-approved Magic illustration quality.  
2. Keep drafts unmerged: #55 (obs) · this migration · #57 maint off `2cbc1ad0`.  
3. Authorize a **separate** maintenance deploy only after quality acceptance — never full `main` BE (excludes #41).  
4. **No additional paid calls** without new authorization. **No deploy from this task.**
