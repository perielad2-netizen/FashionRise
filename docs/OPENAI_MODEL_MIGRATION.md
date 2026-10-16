# OpenAI model migration — gpt-4o-mini → gpt-6-luna

**Repository:** [perielad2-netizen/FashionRise](https://github.com/perielad2-netizen/FashionRise)  
**Status:** code + mocked tests only. **Not production-validated.** Do not treat this as a live API sign-off.

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
- `backend/app/services/sketch_openai.py` — Chat Completions kwargs, `reasoning_effort` only for GPT-6/5, safer empty/refusal handling
- `backend/scripts/check_sketch_ai.py` — print model/effort; **no API key suffix**
- `backend/tests/test_openai_model_migration.py` — mocked contract tests
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
| Reasoning | Send Chat Completions `reasoning_effort` (not Responses `reasoning.effort`). Default **`none`** — sketch jobs are latency-sensitive; Luna supports `none`; function calling is unused. |
| Sampling | Do not send `temperature` / `top_p` (unsupported when effort is not `none`; unused today). |
| Older override | If `OPENAI_MODEL` is still `gpt-4o-*`, omit `reasoning_effort` so a rollback env keeps working. |
| Token budget | Keep **1400** `max_completion_tokens` (this branch; `main` still has 1200). With `effort=none` the budget is visible JSON only. Incomplete JSON still uses the previous `parse_error` fallback and now records `truncated`. |
| Refusals / empty | Fail the job (worker `failed`) instead of storing an empty summary. |
| Image pipeline | `OPENAI_IMAGE_MODEL=gpt-image-1` untouched — Luna does **not** support `/v1/images/edits`. |
| Stub | Empty `OPENAI_API_KEY` still completes jobs with the local stub. |
| SDK | Still `openai>=1.40.0,<2.0.0`. `reasoning_effort` is passed as a Chat Completions keyword. |

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
cd backend && pytest tests/test_openai_model_migration.py -q
```

Covered: default model, env override, request params, vision `image_base64` / `image_url`, JSON keys (`summary`, `cleanup_bullets`, `polish_bullets`, `suggestions`), failed requests, worker stub, worker failure, no secret in logs.

**Not covered:** live OpenAI calls, production quality vs `gpt-4o-mini`, Azure-compatible proxies, real image-edit quality.

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

## Remaining blockers

- No authorized live / paid OpenAI call was made.
- Existing host `.env` files that pin `OPENAI_MODEL=gpt-4o-mini` will keep the deprecated model until someone updates them.
- Quality of Luna JSON vs mini is unmeasured.
