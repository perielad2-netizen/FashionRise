# OpenAI model migration — gpt-4o-mini → gpt-6-luna

**Repository:** [perielad2-netizen/FashionRise](https://github.com/perielad2-netizen/FashionRise)  
**Status:** GPT-6 Luna Chat Completions **synthetic live compatibility VALIDATED** (3/3). **Production deployment NOT PERFORMED.**  
**PR:** [#6](https://github.com/perielad2-netizen/FashionRise/pull/6) against `cursor/magic-look-image-display-77c6`.  
**Depends on:** unmerged Magic Look [PR #1](https://github.com/perielad2-netizen/FashionRise/pull/1). Retargeting onto `main` must be a separate review after #1 merges.  
**Reviewed production baseline:** `f80fc1de6c309318c7ca894842b1b93d3925b9a7` — live preflight fails if `sketch_openai.py`, `config.py`, `requirements.txt`, or `ai_worker.py` change.

## Why

OpenAI announced GPT-4 series deprecations on **2026-10-14**. `gpt-4o-mini` (snapshot `gpt-4o-mini-2024-07-18`) is scheduled to shut down on **14 January 2027**. The documented replacement is **`gpt-6-luna`**.

Sources (official):

- [Deprecations](https://developers.openai.com/api/docs/deprecations)
- [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna)
- [Using GPT-6](https://developers.openai.com/api/docs/guides/latest-model)

## Previous model → replacement

| Role | Before | After |
|------|--------|--------|
| Sketch Chat Completions (`sketch_clean`, `sketch_polish`, `style_suggest`) | `gpt-4o-mini` | `gpt-6-luna` |
| Look image edit / generate | `gpt-image-1` (unchanged) | `gpt-image-1` |
| Embeddings | not used | not used |

Override remains `OPENAI_MODEL`. Production hosts that pin the old name in `.env` must change that variable; the code default alone does not rewrite an existing env file.

## Files updated

- `backend/app/core/config.py` — default `openai_model`, plus `openai_reasoning_effort` and `openai_max_completion_tokens`
- `backend/requirements.txt` — `openai>=1.109.1,<2.0.0` (verified floor)
- `backend/app/services/sketch_openai.py` — per-family reasoning table, incomplete completions fail before image gen
- `backend/scripts/check_sketch_ai.py` — print model/effort; **no API key suffix**
- `backend/tests/test_openai_model_migration.py` — mocked contract tests
- `backend/scripts/eval_gpt6_luna_live.py` — bounded dry-run-first live harness
- `backend/tests/test_gpt6_luna_live_eval.py` — offline harness tests
- `backend/.env.example`, `deploy/env.production.example`
- this document; `docs/00-PROJECT-STATUS.md`

`backend/app/services/ai_worker.py` is unchanged: it still calls `complete_sketch_job` when a key is set, otherwise the stub.

## API compatibility decisions

FashionRise already uses **Chat Completions**, not the Responses API. Official Luna docs list Chat Completions as supported, with **image input** and **structured outputs**.

| Topic | Decision |
|-------|----------|
| Endpoint | Keep `client.chat.completions.create`. No Responses rewrite. |
| JSON | Keep `response_format={"type": "json_object"}`. Schema-strict `json_schema` would be a contract change (`image_prompt` on polish). |
| Vision | Keep `image_url` / `image_base64` inlined as `data:` image parts. |
| Reasoning | Per-family table (not a GPT-5/6 prefix). **Luna default remains `none`.** `gpt-4o*` omits the field. `gpt-6-astra` / `gpt-6.1-sol` + `none` raise `SketchConfigError` (no HTTP request). Unknown models fail closed. |
| Sampling | Do not send `temperature` / `top_p` (unsupported when effort is not `none`; unused today). |
| Older override | If `OPENAI_MODEL` is still `gpt-4o-*`, omit `reasoning_effort` so a rollback env keeps working. |
| Token budget | Keep **1400** `max_completion_tokens`. With `effort=none` that budget is visible JSON only. |
| Incomplete / invalid | `finish_reason=length`, refusals, empty content, and non-object / invalid JSON raise `SketchCompletionError`. The worker stores `failed` + a short sanitized `error_message`. **No look image is generated.** |
| Image pipeline | `OPENAI_IMAGE_MODEL=gpt-image-1` untouched — Luna does **not** support `/v1/images/edits`. Only a complete JSON object may call `images.edit` / `images.generate`. |
| Stub | Empty `OPENAI_API_KEY` still completes jobs with the local stub. |
| SDK | **`openai>=1.109.1,<2.0.0`**. `reasoning_effort` first appeared in 1.58.0; this repo validated the keyword on **1.109.1**. That version’s typed alias is `minimal\|low\|medium\|high`; Luna’s documented `none` is still sent as the Chat Completions string. |

## Pricing / cost (documented list prices, not measured)

Per 1M text tokens, Standard:

| Model | Input | Cached input | Output |
|-------|-------|--------------|--------|
| `gpt-4o-mini` | $0.15 | $0.075 | $0.60 |
| `gpt-6-luna` | $0.10 | $0.01 | $0.50 |

Luna is cheaper **per token**. Default Luna reasoning effort is **medium**; this integration sets **`none`** so we do not pay for unused hidden reasoning on short JSON tips. Prompts over 272K input tokens on Luna are billed at 2× input / 1.5× output — FashionRise sketch notes plus one image are far below that.

Latency should stay in the same class as mini **if** `reasoning_effort=none`. A production host that removes that setting will see more tokens and higher latency.

## Verification (mocked)

```text
cd backend && pytest tests/test_openai_model_migration.py tests/test_gpt6_luna_live_eval.py -q
# 55 passed (mocked; openai 1.109.1 installed)

cd backend && pytest tests -q
# 55 passed, 7 ERROR at setup (PostgreSQL connection refused)

cd backend && python3 scripts/eval_gpt6_luna_live.py
# dry-run; 0 network calls
```

Covered (mocked): default model, env override, Luna `none`, gpt-4o-mini omit, Astra / GPT-6.1 Sol reject `none` and accept `low`, unknown models (`gpt-5*`, bare `gpt-6`) fail closed, SDK floor + `Completions.create` signature (`reasoning_effort`, `response_format`, `max_completion_tokens`), vision `image_base64` / `image_url`, JSON keys (`summary`, `cleanup_bullets`, `polish_bullets`, `suggestions`), successful `image_prompt`, truncated/empty/invalid/refused polish never call `images.edit` / `images.generate` (including `finish_reason=length` even when JSON parses), worker stub, worker failure, no secret in logs, dry-run harness, missing ack/key, unexpected `OPENAI_BASE_URL`, returned-model mismatch, missing usage, invalid JSON, sanitized provider errors, budget stop, CONDITIONAL quality, unreviewed integration baseline block, bounded `review_output` on success, unknown spend when usage is missing.

**Lint / types:** `python3 -m compileall -q app tests scripts` succeeded. No `ruff` or `mypy` is configured in this repo.

**NOT RUN (do not treat as passed):** PostgreSQL integration tests — `test_api_surface`, `test_user_flow_api` (3), `test_design_handoff` (2), `test_health`. This environment has no Postgres; they ERROR at fixture setup (`connection refused`).

**Not covered:** production traffic / customer assets, independent isolation of vision vs written notes, image-edit quality, Azure-compatible proxies, PostgreSQL-backed API tests.

## Production configuration (manual)

Do **not** apply these from this change set. After review:

1. Set `OPENAI_MODEL=gpt-6-luna` (or omit it and take the new default after deploy).
2. Set `OPENAI_REASONING_EFFORT=none` unless evals justify more.
3. Leave `OPENAI_IMAGE_MODEL=gpt-image-1`.
4. Restart the API / `python -m app.ai_worker`.
5. Confirm with `python scripts/check_sketch_ai.py` (prints model, never the key).

## Rollback

1. Set `OPENAI_MODEL=gpt-4o-mini` in the host `.env` (no code revert required for the model string).
2. Restart the worker. `reasoning_effort` is omitted automatically for `gpt-4o-*`.
3. After **14 January 2027**, `gpt-4o-mini` will not accept new requests — rollback only works until shutdown.

## Bounded live evaluation (harness hardened; dry-run only)

Harness: `backend/scripts/eval_gpt6_luna_live.py`

The script reuses production `build_sketch_chat_request` and `_parse_chat_completion`. It never calls `complete_sketch_job`. Image model is treated as `off`. `images.edit` / `images.generate` raise. `max_retries=0`. Live traffic is locked to `https://api.openai.com/v1` (unexpected `OPENAI_BASE_URL`, including Azure/proxies, is rejected). Application proxy support is unchanged. No database, email, production assets, or customer images.

Live preflight also requires:
- branch `cursor/openai-gpt6-luna-77c6`
- reviewed baseline `f80fc1de6c309318c7ca894842b1b93d3925b9a7` is an ancestor
- `sketch_openai.py`, `config.py`, `requirements.txt`, and `ai_worker.py` identical to that baseline (committed and uncommitted)
- returned model is `gpt-6-luna` (or a `gpt-6-luna-*` snapshot)
- each response includes valid `prompt_tokens` and `completion_tokens`
- cumulative estimated spend plus the next conservative request stays ≤ **$0.05**
- provider failures are classified (auth / rate-limit / timeout / network / invalid-request / unexpected) without raw bodies, credentials, headers, or image data
- remaining scenarios are marked **NOT RUN**; the run outcome is **FAIL** (never a silent PASS)

Outcomes distinguish **API compatibility**, **JSON contract**, **automated quality** (`PASS` / `CONDITIONAL` / `FAIL`), and **human review still required**. Weak vocabulary, generic advice, or poor sketch relevance yields **CONDITIONAL**, not an unconditional PASS. Production JSON contracts are unchanged.

Each **contract-validated** live scenario now includes a bounded `review_output` for human review (Unicode preserved; extra keys dropped; text and list sizes clipped):

| Scenario | `review_output` fields |
|----------|------------------------|
| `sketch_clean` | `summary`, `cleanup_bullets` |
| `sketch_polish` | `summary`, `polish_bullets`, `image_prompt` |
| `style_suggest` | `summary`, `suggestions` (`title`, `description`) |

Failed or unvalidated responses do **not** persist raw model content. If usage tokens are missing, `estimated_spend_usd` is **unknown** (not `$0`).

**Default remains dry-run.** Do **not** repeat the live test. Client-side USD figures are **not an absolute billing guarantee**.

```text
# Dry-run (safe; default)
cd backend && python3 scripts/eval_gpt6_luna_live.py
```

### Dry-run result (2026-10-16, after harness safety amendment)

| Check | Result |
|-------|--------|
| Branch | `cursor/openai-gpt6-luna-77c6` |
| Reviewed production baseline | `f80fc1de6c309318c7ca894842b1b93d3925b9a7` (files unchanged) |
| Model / effort / tokens | `gpt-6-luna` / `none` / `1400` |
| Endpoint | `https://api.openai.com/v1` |
| Planned Chat Completions | **3** |
| Planned `images.edit` / `images.generate` | **0 / 0** |
| Vision attached | clean=yes, polish=yes, style=no |
| Estimated total USD | **$0.002382** (text + 3× vision tiles + 250-token overhead + 1400 output × 3; **not a billing guarantee**) |
| Budget ceiling | $0.05 |
| Live requests made | **0** |
| `OPENAI_API_KEY` in this environment | unset |

Per-request conservative estimates:

| Scenario | Text | Vision | Overhead | Budgeted output | Est. USD |
|----------|------|--------|----------|-----------------|----------|
| `sketch_clean` | 162 | 765 | 250 | 1400 | $0.000818 |
| `sketch_polish` | 219 | 765 | 250 | 1400 | $0.000823 |
| `style_suggest` | 159 | 0 | 250 | 1400 | $0.000741 |

### Scenario contract (eval-only; stricter than the production parser)

| Scenario | Required keys | Synthetic live quality |
|----------|---------------|------------------------|
| `sketch_clean` | `summary`; `cleanup_bullets` 3–7 nonempty | **PASS / ACCEPTED** (2026-10-16) |
| `sketch_polish` | `summary`; `polish_bullets` 3–5 nonempty; `image_prompt` relevant to the A-line dress | **PASS / ACCEPTED** (2026-10-16) |
| `style_suggest` | `summary`; exactly 5 `suggestions` with nonempty title+description | **PASS / ACCEPTED** (2026-10-16) |

## Operator-supplied live execution report (2026-10-16)

**Source:** operator-run `--execute --acknowledge-paid-test` on the approved synthetic harness.  
**Review:** PM reviewed the harness report and initial human-quality check.  
**This agent did not execute the live test and must not repeat it.**  
Recorded measurements below are copied from that operator report. No additional model text was invented.

| Field | Result |
|-------|--------|
| Model | `gpt-6-luna` |
| Reasoning effort | `none` |
| Chat Completions | **3** |
| Image edit / generate | **0 / 0** |
| Vision inputs | **2** (`sketch_clean`, `sketch_polish`) |
| Overall outcome | **PASS** |
| API compatibility | **PASS** |
| JSON contract | **PASS** |
| Automated quality | **PASS** |
| Initial human review | **ACCEPTED** |
| Input tokens | **472** |
| Output tokens | **555** |
| Reasoning tokens | **0** |
| Observed estimated cost | **$0.000325** (not a billing guarantee) |
| Preflight cost estimate | $0.002382 |
| Spending ceiling | $0.05 |

### 1. `sketch_clean` — PASS / ACCEPTED

| | |
|--|--|
| Input / output tokens | 163 / 173 |
| Latency | 4858 ms |
| Estimated cost | $0.000103 |

Summary (operator report):

> The sketch reads as a simple A-line day dress; refining the outline and figure proportions will make the design easier to read.

Six recommendations addressed (operator/PM summary, not reconstructed verbatim JSON):

- Smooth balanced boat neckline
- Clean shoulder, sleeve, side and hem lines
- Symmetric A-line flare and level hem
- Consistent short sleeves
- Figure/head-to-hem proportions
- Construction guides and final contours

### 2. `sketch_polish` — PASS / ACCEPTED

| | |
|--|--|
| Input / output tokens | 192 / 150 |
| Latency | 2702 ms |
| Estimated cost | $0.000094 |

Summary (operator report):

> Your clean A-line silhouette is a great start— let's make the sketch portfolio-ready!

Five recommendations addressed (operator/PM summary):

- Preserve boat neck, short sleeves and knee hem
- Smooth balanced garment outline
- Refine waist seam and A-line silhouette
- Improve line-weight variation
- Remove construction marks and center sketch

Image prompt (operator report):

> Front-facing figure with a simple oval head and short horizontal brim hat, boat neckline, short sleeves, fitted waist seam, A-line dress shape, straight knee-length hem, and simple legs.

### 3. `style_suggest` — PASS / ACCEPTED

| | |
|--|--|
| Input / output tokens | 117 / 232 |
| Latency | 3985 ms |
| Estimated cost | $0.000128 |

Suggestion titles (operator report):

- Seaside Blue A-Line
- Coral Breeze
- Sandy Stripe
- Mint Garden
- Lavender Coast

Human note: age-appropriate and consistent with the brief. Most variations emphasize colors and accessories, not silhouette changes. **Not a migration blocker.**

### Remaining limitations (still true after this live run)

- Validates **synthetic** harness requests, not production jobs or customer assets.
- Vision input was accepted; independent visual understanding was **not** conclusively isolated from the written notes.
- Image generation / edit was **not** evaluated (0 calls, as required).
- PostgreSQL-backed integration tests remain **NOT RUN**.
- Magic Look **PR #1** remains unmerged. PR #6 cannot land on `main` until that is resolved or a separately reviewed retarget is done.
- No deployment and no production `.env` change.

## Remaining blockers

- Production deployment **NOT PERFORMED**. Host `.env` files that still pin `OPENAI_MODEL=gpt-4o-mini` keep the deprecated model until updated.
- Magic Look **PR #1** is still unmerged. PR #6 stays based on `cursor/magic-look-image-display-77c6`.
- PostgreSQL-backed API tests are **NOT VALIDATED**.
- Do not repeat the paid live harness run.

## Exact next action

**Next release gate:** resolve Magic Look PR #1 (or a separately reviewed retarget of #6 onto `main`) **and** run the PostgreSQL integration tests. Do not deploy or edit production `.env` as part of this documentation update. Do not repeat the live OpenAI test.
