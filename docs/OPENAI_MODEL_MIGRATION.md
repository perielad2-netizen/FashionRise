# OpenAI model migration — gpt-4o-mini → gpt-6-luna

**Repository:** [perielad2-netizen/FashionRise](https://github.com/perielad2-netizen/FashionRise)  
**Status:** code + mocked tests + **dry-run live harness**. **Not production-validated.** No paid OpenAI call has been authorized or executed.  
**PR:** [#6](https://github.com/perielad2-netizen/FashionRise/pull/6) (draft) against `cursor/magic-look-image-display-77c6`.  
**Depends on:** unmerged Magic Look [PR #1](https://github.com/perielad2-netizen/FashionRise/pull/1). Retargeting onto `main` must be a separate review after #1 merges.

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
# 44 passed (mocked; openai 1.109.1 installed)

cd backend && pytest tests -q
# 44 passed, 7 ERROR at setup (PostgreSQL connection refused)

cd backend && python3 scripts/eval_gpt6_luna_live.py
# dry-run; 0 network calls
```

Covered (mocked): default model, env override, Luna `none`, gpt-4o-mini omit, Astra / GPT-6.1 Sol reject `none` and accept `low`, unknown models (`gpt-5*`, bare `gpt-6`) fail closed, SDK floor + `Completions.create` signature (`reasoning_effort`, `response_format`, `max_completion_tokens`), vision `image_base64` / `image_url`, JSON keys (`summary`, `cleanup_bullets`, `polish_bullets`, `suggestions`), successful `image_prompt`, truncated/empty/invalid/refused polish never call `images.edit` / `images.generate` (including `finish_reason=length` even when JSON parses), worker stub, worker failure, no secret in logs, dry-run harness, image-endpoint guard, `--execute` without ack refused.

**Lint / types:** `python3 -m compileall -q app tests scripts` succeeded. No `ruff` or `mypy` is configured in this repo.

**NOT RUN (do not treat as passed):** PostgreSQL integration tests — `test_api_surface`, `test_user_flow_api` (3), `test_design_handoff` (2), `test_health`. This environment has no Postgres; they ERROR at fixture setup (`connection refused`).

**Not covered:** live OpenAI calls (harness ready; spend not authorized), production quality vs `gpt-4o-mini`, Azure-compatible proxies, real image-edit quality.

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

## Bounded live evaluation (dry-run completed)

Harness: `backend/scripts/eval_gpt6_luna_live.py`

The script reuses `sketch_openai.build_sketch_chat_request` (production system prompts + vision inlining + `chat_completion_kwargs`) and `sketch_openai._parse_chat_completion`. It never calls `complete_sketch_job`, so polish cannot reach look-image generation. `OPENAI_IMAGE_MODEL` is treated as `off`. `client.images.edit` / `client.images.generate` raise `EvalGuardError`. SDK `max_retries=0`. No database, email, production assets, or customer images. Synthetic 160×240 PNG croquis are generated in-process and attached only as `image_base64` for `sketch_clean` and `sketch_polish`.

**Default is dry-run (zero network).** This document and the PR review prompt are **not** authorization to spend.

```text
# Dry-run (safe; default)
cd backend && python3 scripts/eval_gpt6_luna_live.py

# Live — only if an operator separately authorizes spend
cd backend && python3 scripts/eval_gpt6_luna_live.py --execute --acknowledge-paid-test
```

`--execute` without `--acknowledge-paid-test` exits 2 and makes no request. Live mode reads `OPENAI_API_KEY` from the **process environment only** (not `backend/.env`) and never prints the key.

### Dry-run result (2026-10-16)

| Check | Result |
|-------|--------|
| Branch | `cursor/openai-gpt6-luna-77c6` |
| Reviewed ancestor | `3b0abb1ff62cd1c9fc1b3ef1d2b41d39057e8332` |
| Model / effort / tokens | `gpt-6-luna` / `none` / `1400` |
| Planned Chat Completions | **3** |
| Planned `images.edit` / `images.generate` | **0 / 0** |
| Vision attached | clean=yes, polish=yes, style=no |
| Estimated total USD | **$0.002256** (worst-case 1400 output tokens × 3; **not a billing guarantee**) |
| Budget ceiling | $0.05 |
| Live requests made | **0** |
| `OPENAI_API_KEY` in this environment | unset |

Per-request client-side estimates (input overestimate + 1400 budgeted output tokens):

| Scenario | Est. input tokens | Budgeted output | Est. USD |
|----------|-------------------|-----------------|----------|
| `sketch_clean` (vision) | 672 | 1400 | $0.000767 |
| `sketch_polish` (vision) | 729 | 1400 | $0.000773 |
| `style_suggest` (text) | 159 | 1400 | $0.000716 |

### Scenario contract (eval-only; stricter than the production parser)

| Scenario | Required keys | Live quality |
|----------|---------------|--------------|
| `sketch_clean` | `summary`; `cleanup_bullets` 3–7 nonempty | **NOT RUN** |
| `sketch_polish` | `summary`; `polish_bullets` 3–5 nonempty; `image_prompt` relevant to the A-line dress | **NOT RUN** |
| `style_suggest` | `summary`; exactly 5 `suggestions` with nonempty title+description | **NOT RUN** |

Production `_parse_chat_completion` still accepts any JSON object and then the worker stores it. The harness does **not** change that business behavior. No output-contract defect was found in dry-run that requires a production code change.

### Quality review

Not performed. A valid JSON object alone would not be a passing live result. Live scoring (relevance, fashion terminology, actionable advice, vision understanding, latency, tokens) waits for a separately authorized `--execute --acknowledge-paid-test` run.

## Remaining blockers

- **Live / paid OpenAI eval was not run.** The harness is ready; spend was not authorized.
- Existing host `.env` files that pin `OPENAI_MODEL=gpt-4o-mini` will keep the deprecated model until someone updates them.
- Quality of Luna JSON vs mini is unmeasured.
- PR #6 cannot land on `main` until Magic Look PR #1 is merged (or a separately reviewed retarget).
- Postgres-backed API tests were **NOT RUN**.

## Exact next action

An operator who **separately authorizes spend** should export `OPENAI_API_KEY` in the process environment and run:

```text
cd backend && python3 scripts/eval_gpt6_luna_live.py --execute --acknowledge-paid-test
```

Do not merge, deploy, rebase/retarget PR #6, or edit production `.env` until that live eval passes quality review. Do not treat this document as spend authorization.
