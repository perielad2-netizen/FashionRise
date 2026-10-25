# WEB-V4J Stage B — persistence readiness (maint lineage)

**Issue:** [#42](https://github.com/perielad2-netizen/FashionRise/issues/42)  
**Stage A:** PR [#67](https://github.com/perielad2-netizen/FashionRise/pull/67) accepted (docs; not merge-authorized).  
**Base:** exact production maint tip `12f7acdff9133e810c0d670697d1500e860f39d6` (not `main`).  
**Scope:** Backend `design_service` only — `draft.v2` / `saved_design.v2` fingerprint, validation, reject-on-downgrade, OCC/idempotency.  
**Explicit non-scope:** no deploy, no service restart, no Alembic, no FE Back UI, no rear PNG, no paid AI, no Magic worker changes, no Nginx/Cloudflare.

## Implementation summary

| Concern | Behavior |
|---------|----------|
| Studio classification | Recognizes `fashionrise.studio.draft.v1` **and** `.v2` (plus `draftKind`) for stored and incoming |
| Fingerprint | Includes `schema`, `activeSide` (default `front`), absent-vs-empty `back` sentinel, front strokes/fills/model/brush/dimmed/custom refs |
| Create/reconcile | Downgrade / back-strip / `studioSides<2` rejected **before** same-content or stale-revision shortcuts |
| Update/OCC | Same guards before idempotent short-circuit; back-only edits advance fingerprint + revision |
| Saved designs | `saved_design.v2` validated; `saveRequestId` idempotent create; content immutable (no v2→v1 rewrite) |
| Migration | None |

## Verification (this PR head)

| Gate | Result |
|------|--------|
| Focused Stage B suite | `tests/test_studio_draft_v2_persistence.py` — **21 passed** |
| Studio + saved isolation | prior suites + Stage B — **46 passed** |
| Full backend pytest | **378 passed** (maint tip baseline was 357 + 21 new) |
| Ruff (changed files) | Clean aside from **pre-existing** UP017/UP012 in handoff PDF helpers (unchanged logic) |
| Mypy `design_service.py` | No new errors; pre-existing `app/storage/local.py` Path/`None` remain |

## Proposed later production release plan (NOT authorized now)

1. Technical PM code review of this draft PR.  
2. Tag/release candidate from this maint tip lineage only (never from undeployed `main` PR #41 packing).  
3. Authorized BE+worker restart onto the Stage B SHA with Alembic still `005`.  
4. Smoke: v1 draft create/update idempotency; synthetic v2 fixture reject old-client strip (staging or controlled probe).  
5. Only then enable Stage C artwork / Stage D FE dual-reader work.

**STOP:** No merge/deploy from this readiness note alone.
