# WEB-V4J Stage C — dual-side Magic orchestration (maint lineage)

**Issue:** [#42](https://github.com/perielad2-netizen/FashionRise/issues/42) · **Draft PR:** [#70](https://github.com/perielad2-netizen/FashionRise/pull/70)  
**Base:** Stage B approved tip `6b253cb52beb9524f976ba805049bf3de2506985` on `cursor/web-v4j-c-dual-magic-77c6` (descendant of `12f7acdf…`, **not** `main`).  
**Companion FE:** PR [#69](https://github.com/perielad2-netizen/FashionRise/pull/69) — Front/Back editor + Dual Magic client gate + linked `/polish` retry with persisted per-attempt idempotency keys.  
**Scope:** Backend Magic orchestration — `POST /ai/sketch/polish-dual`, linked `POST /ai/sketch/polish` (when `magic_operation_id` + `studio_side` present), sketch_polish identity fields, owner-scoped `pg_advisory_xact_lock`, `GET /ai/magic-operations/{id}/jobs`, side-aware `sketch_openai` prompts **without** PR #41 `pose_lock` packing.  
**Explicit non-scope:** no production deploy, no Dual Magic flag-on, no Nginx allowlist change, no paid OpenAI, no Alembic migration, no undeployed `main` / PR #41 pose packing.

## API summary

| Endpoint | Behavior |
|----------|----------|
| `POST /api/v1/ai/sketch/polish` | Ordinary one-sided enqueue unchanged when unlinked. **Linked** attempts (`magic_operation_id` + `studio_side`) **require** `idempotency_key` and `source_revision` or `content_fingerprint`; use owner advisory lock + one-active-attempt-per-side reconcile; same key returns original job (incl. **failed**); new key allowed only after prior failure with matching garment/design identity (raster re-capture of the same document is allowed). |
| `POST /api/v1/ai/sketch/polish-dual` | **Requires** client `magic_operation_id`, per-side non-empty `idempotency_key` (front ≠ back), `shared_garment_spec`, and `source_revision` **or** `content_fingerprint`. Returns `magic_operation_id`, `front_job`, `back_job`. |
| `GET /api/v1/ai/magic-operations/{magic_operation_id}/jobs` | Owner-scoped recovery list (oldest-first). Clients select **latest** attempt per side. |

### Idempotency design (no new DB index)

1. Per-owner `pg_advisory_xact_lock` serializes dual enqueue and linked `/polish` attempts.  
2. Lookup existing `sketch_polish` by `input_data.idempotency_key` for statuses `queued` \| `running` \| `completed` \| `failed`.  
3. Same-key hit → compare full attempt identity (side, operation, design, revision/fingerprint, image hash, prompt). Mismatch → **409**.  
4. New key while side is queued/running/completed → **409** (`operation_side_active`).  
5. New key after failed side → allowed only if garment/design identity matches (excludes per-side notes and allows new raster of the same Studio document).  
6. Lost-response recovery: repeat the same key + matching identity, or `GET` operation jobs — never invent a new key automatically.

## Verification (offline)

| Gate | Result |
|------|--------|
| Focused suite | `tests/test_dual_magic_orchestration.py` — **26 passed** (incl. linked `/polish` retry + mocked e2e complete/retry/recover) |
| Companion FE | PR #69 focused Vitest for linked retry fields + `retryMagicSide` idempotency + Dual Magic gate |
| Alembic | Head **`005`** — no new revision |
| Paid OpenAI | **0** |

## Production activation (NOT authorized now)

Production baseline to preserve until separate authorize:

- FE `4589a62d…` (Front/Back LIVE, `VITE_STUDIO_DUAL_MAGIC_ENABLED=false`)
- BE Stage B `6b253cb5…`
- Alembic `005`

When authorized later: deploy this PR tip (maint lineage only) + FE with Dual Magic flag ON; extend Nginx allowlist for `polish-dual` + magic-operations GET; no paid smoke without explicit approval.

**STOP:** Ready for controlled release review. Do **not** deploy or enable the Dual Magic flag from this document alone.
