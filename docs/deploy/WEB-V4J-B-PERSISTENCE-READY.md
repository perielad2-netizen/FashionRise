# WEB-V4J Stage B — persistence readiness (maint lineage)

**Issue:** [#42](https://github.com/perielad2-netizen/FashionRise/issues/42)  
**Stage A:** PR [#67](https://github.com/perielad2-netizen/FashionRise/pull/67) accepted (docs; not merge-authorized).  
**Base branch (immutable):** `cursor/maint-base-12f7acdf-77c6` → `12f7acdff9133e810c0d670697d1500e860f39d6` (not `main`).  
**Scope:** Backend `design_service` only — `draft.v2` / `saved_design.v2` fingerprint, validation, reject-on-downgrade, OCC/idempotency, explicit Back clear intent.  
**Explicit non-scope:** no deploy, no service restart, no Alembic, no FE Back UI, no rear PNG, no paid AI, no Magic worker changes, no Nginx/Cloudflare.

## Implementation summary

| Concern | Behavior |
|---------|----------|
| Studio classification | Recognizes `fashionrise.studio.draft.v1` **and** `.v2` (plus `draftKind`) for stored and incoming; unknown schemas fail closed |
| Fingerprint | Includes `schema`, `activeSide` (default `front`), absent-vs-empty `back` sentinel, front strokes/fills/model/brush/dimmed/custom refs |
| Create/reconcile | Downgrade / back-strip / clear-without-intent / `studioSides<2` rejected **before** same-content or stale-revision shortcuts |
| Update/OCC | Same guards before idempotent short-circuit; back-only edits advance fingerprint + revision |
| Clear Back | Non-empty → empty Back requires `clearBackIntent=true` (metadata or design_data) + valid OCC; accidental empty payload → 409 |
| Saved designs | Strict envelope/snapshot/`back` keys; full-envelope fingerprint; `saveRequestId` idempotent create under owner advisory lock; stored-kind immutability (no studio hijack via PUT) |
| Kind integrity | Bidirectional: saved→studio and studio→saved (incl. metadata-only `designKind`) rejected; mixed-kind create → 422 |
| Unknown schemas | `fashionrise.studio.draft.*` / `fashionrise.saved_design.*` unknown versions → 422 even without kind metadata |
| Migration | None — Alembic head remains `005` |

## Verification (this PR head)

| Gate | Result |
|------|--------|
| Focused Stage B suite | `tests/test_studio_draft_v2_persistence.py` — **32 passed** |
| Full backend pytest | **389 passed** |
| Ruff (new findings) | None on Stage B logic; **pre-existing** UP017/UP012 in handoff PDF helpers only |
| Mypy `design_service.py` | No new errors; pre-existing `app/storage/local.py` Path/`None` remain |
| Alembic heads | `005 (head)` — no new revision |

## Proposed later production release plan (NOT authorized now)

1. Technical PM code review of draft PR #68.  
2. Deploy **only** from this maint lineage (base `cursor/maint-base-12f7acdf-77c6` + Stage B commit), never from undeployed `main` PR #41 packing.  
3. Authorized BE+worker restart onto the Stage B SHA; Alembic stays `005`; FE stays `a740a9b7` (V1-only clients remain compatible — Stage B dormant).  
4. Smoke: v1 draft create/update idempotency; synthetic v2 fixture proves old-client strip → 409.  
5. Rollback: revert API/worker symlink/process to prior tip `12f7acdf` (or previous release tag); no DB migrate down required.  
6. Only then Stage C artwork / Stage D FE dual-reader.

**STOP:** No merge/deploy from this readiness note alone.
