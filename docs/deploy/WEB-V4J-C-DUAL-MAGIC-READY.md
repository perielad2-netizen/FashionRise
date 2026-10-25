# WEB-V4J Stage C — dual-side Magic orchestration (maint lineage)

**Issue:** [#42](https://github.com/perielad2-netizen/FashionRise/issues/42) · **Draft PR:** [#70](https://github.com/perielad2-netizen/FashionRise/pull/70)  
**Base:** Stage B approved tip `6b253cb52beb9524f976ba805049bf3de2506985` on `cursor/web-v4j-c-dual-magic-77c6` (descendant of `12f7acdf…`, **not** `main`).  
**Scope:** Backend Magic orchestration — `POST /ai/sketch/polish-dual`, sketch_polish `input_data` fields (`studio_side`, `magic_operation_id`, per-side `idempotency_key`, `source_revision` / `content_fingerprint`, `image_fingerprint`, `shared_garment_spec`, `reference_model_id`), owner-scoped `pg_advisory_xact_lock` + JSONB idempotency lookup, identity-bound recovery (`409` on mismatch), `GET /ai/magic-operations/{id}/jobs`, side-aware `sketch_openai` prompts **without** PR #41 `pose_lock` packing.  
**Explicit non-scope:** no deploy, no Nginx allowlist change, no FE Back UI, no rear croquis PNG artwork, no paid OpenAI, no Alembic migration, no `design_data` raster reads, no `design_service` Stage B edits.

## API summary

| Endpoint | Behavior |
|----------|----------|
| `POST /api/v1/ai/sketch/polish` | One-sided enqueue; optional `idempotency_key` with identity binding (`studio_side`, `magic_operation_id`, `design_id`, revision/fingerprint, `image_fingerprint`) when key present. |
| `POST /api/v1/ai/sketch/polish-dual` | **Requires** client `magic_operation_id`, per-side non-empty `idempotency_key` (front ≠ back), `shared_garment_spec` (bounded object), and `source_revision` **or** `content_fingerprint`. Returns `magic_operation_id`, `front_job`, `back_job`. Failed jobs are **not** idempotent hits — retry failed side with a **new** back/front key. |
| `GET /api/v1/ai/magic-operations/{magic_operation_id}/jobs` | Owner-scoped recovery list for one coordinated run (`queued` / `completed`; worker has no separate `processing` state today). |

### Job status vocabulary

Worker transitions: `queued` → `completed` or `failed`. There is no persisted `processing` status in the current worker; clients should poll `GET /jobs/{id}` or the magic-operation list until `completed` or `failed`.

### Idempotency design (no new DB index)

1. Per-owner `pg_advisory_xact_lock` serializes dual enqueue (distinct key from Studio/saved locks).  
2. Under lock, lookup existing `sketch_polish` rows by `input_data.idempotency_key` for statuses `queued` \| `completed` only.  
3. On hit, compare stored identity tuple: `studio_side`, `magic_operation_id`, `design_id`, `source_revision` / `content_fingerprint`, `image_fingerprint` (SHA-256 of raster bytes or image URL). Mismatch → **409**. Cross-side key reuse → **422** at parse time or **409** at reconcile.  
4. Lost-response recovery: repeat the same keys + matching identity → same job ids (dual POST or GET by `magic_operation_id`).

## Verification (offline)

| Gate | Result |
|------|--------|
| Focused suite | `tests/test_dual_magic_orchestration.py` — **19 passed** |
| Full backend pytest | **408 passed** (`DATABASE_URL_TEST` disposable DB) |
| Ruff (touched) | Clean on changed modules; pre-existing `B008` on FastAPI `Depends` in `ai_routes.py` |
| Mypy (touched modules) | No new errors in changed files; pre-existing `app/storage/local.py` remains |
| Alembic | Head **`005`** — no new revision |

## Proposed later production plan (NOT authorized now)

1. Technical PM review after Stage B deploy path is settled.  
2. Authorized BE+worker deploy from maint lineage only (never undeployed `main` / PR #41 pose packing).  
3. Extend Nginx AI allowlist for `POST /api/v1/ai/sketch/polish-dual` and `GET /api/v1/ai/magic-operations/*` when FE Stage D ships.  
4. Operator dual-side Magic acceptance with paid generation (separate authorization).  

**STOP:** This readiness note does not authorize merge or deploy.
