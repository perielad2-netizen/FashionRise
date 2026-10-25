# WEB-V4J Stage C — dual-side Magic orchestration (maint lineage)

**Issue:** [#42](https://github.com/perielad2-netizen/FashionRise/issues/42)  
**Base:** Stage B approved tip `6b253cb52beb9524f976ba805049bf3de2506985` on `cursor/web-v4j-c-dual-magic-77c6` (descendant of `12f7acdf…`, **not** `main`).  
**Scope:** Backend Magic orchestration — `POST /ai/sketch/polish-dual`, sketch_polish `input_data` fields (`studio_side`, `magic_operation_id`, `idempotency_key`, `shared_garment_spec`, `reference_model_id`), JSONB idempotency lookup, side-aware `sketch_openai` prompts **without** PR #41 `pose_lock` packing.  
**Explicit non-scope:** no deploy, no Nginx allowlist change, no FE Back UI, no rear croquis PNG artwork, no paid OpenAI, no Alembic migration, no `design_data` raster reads.

## API summary

| Endpoint | Behavior |
|----------|----------|
| `POST /api/v1/ai/sketch/polish` | Unchanged one-sided enqueue; optional dual fields on `input_data` for sequential front/back POSTs linked by `magic_operation_id`. |
| `POST /api/v1/ai/sketch/polish-dual` | One request with `front` + `back` image payloads and shared fields; returns `magic_operation_id`, `front_job`, `back_job`. Per-side `idempotency_key` dedupes queued/completed jobs. |

## Verification (offline)

| Gate | Result |
|------|--------|
| Focused suite | `tests/test_dual_magic_orchestration.py` — **12 passed** |
| Full backend pytest | **401 passed** (`DATABASE_URL_TEST` disposable DB) |
| Ruff (touched) | Clean after import/test fixes; pre-existing `B008` on FastAPI `Depends` in `ai_routes.py` |
| Mypy (touched modules) | No new errors in changed files; pre-existing `app/storage/local.py` remains |
| Alembic | Head **`005`** — no new revision |

## Proposed later production plan (NOT authorized now)

1. Technical PM review after Stage B deploy path is settled.  
2. Authorized BE+worker deploy from maint lineage only (never undeployed `main` / PR #41 pose packing).  
3. Extend Nginx AI allowlist for `POST /api/v1/ai/sketch/polish-dual` when FE Stage D ships.  
4. Operator dual-side Magic acceptance with paid generation (separate authorization).  

**STOP:** This readiness note does not authorize merge or deploy.
