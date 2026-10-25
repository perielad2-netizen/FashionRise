# WEB-V4J Stage B — persistence readiness (maint lineage)

**Issue:** [#42](https://github.com/perielad2-netizen/FashionRise/issues/42)  
**Stage A:** PR [#67](https://github.com/perielad2-netizen/FashionRise/pull/67) accepted (docs; not merge-authorized).  
**Base branch (immutable):** `cursor/maint-base-12f7acdf-77c6` → `12f7acdff9133e810c0d670697d1500e860f39d6` (not `main`).  
**Candidate HEAD:** `6b253cb52beb9524f976ba805049bf3de2506985`  
**Technical PM source review:** **ACCEPTED** (2026-10-25) — controlled release planning authorized; **deploy / merge / ready-for-review NOT authorized**.  
**Scope:** Backend `design_service` only — `draft.v2` / `saved_design.v2` fingerprint, validation, reject-on-downgrade, OCC/idempotency, explicit Back clear intent, bidirectional kind integrity.  
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
| GitHub CI check-runs at HEAD | **None** (not independently confirmed by Actions) |

## Release planning (read-only)

SHA-pinned preflight + cutover + rollback checklist:  
[`docs/deploy/WEB-V4J-B-RELEASE-PLAN.md`](./WEB-V4J-B-RELEASE-PLAN.md)

Summary constraints retained here:

1. Deploy **only** maint lineage tip `6b253cb5` (base `12f7acdf`), never undeployed `main` / PR #41.  
2. Authorized BE(+worker tree) restart onto that SHA only after **separate** operator deploy auth; Alembic stays `005`; FE stays `a740a9b7`.  
3. Synthetic V1/V2 smoke only; no paid AI.  
4. Rollback to exact `12f7acdf`; no DB migrate down.  
5. Stage C artwork / Stage D FE remain gated after a successful authorized BE release.

**STOP:** PM acceptance ≠ merge/deploy authorization. Do not execute the release plan without a separate explicit operator GO.
