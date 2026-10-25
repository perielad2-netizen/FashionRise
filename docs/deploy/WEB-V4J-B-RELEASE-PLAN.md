# WEB-V4J Stage B — SHA-pinned backend maintenance release plan

**Status:** Read-only planning document for separate operator authorization.  
**Technical PM source review:** **ACCEPTED** on draft PR [#68](https://github.com/perielad2-netizen/FashionRise/pull/68) at HEAD `6b253cb52beb9524f976ba805049bf3de2506985` (2026-10-25).  
**Deploy authorization:** **NOT granted.** Do **not** merge, mark ready, restart services, or modify VPS/production data from this document alone.

**Issue:** [#42](https://github.com/perielad2-netizen/FashionRise/issues/42) — remains OPEN.  
**Cursor paid AI:** **0** (no paid calls in Stage B; none authorized for release smoke).

## Pinned SHAs

| Artifact | Exact SHA / value |
|---|---|
| Stage B candidate (API tree tip) | `6b253cb52beb9524f976ba805049bf3de2506985` |
| Immutable maint base / rollback tip | `12f7acdff9133e810c0d670697d1500e860f39d6` |
| PR base branch | `cursor/maint-base-12f7acdf-77c6` (not GitHub `main`) |
| Production FE (must remain) | `a740a9b7` |
| Production BE/worker (current, last reported) | `12f7acdf…` |
| Alembic | **`005`** (no migration in this release) |

**Diff scope (candidate vs base):** only

- `backend/app/services/design_service.py`
- `backend/tests/test_studio_draft_v2_persistence.py`
- `docs/00-PROJECT-STATUS.md`
- `docs/deploy/WEB-V4J-B-PERSISTENCE-READY.md`
- (plus this release-plan doc when present on the tip)

## Hard rules

1. Deploy **only** the maint-lineage candidate tip above — never undeployed GitHub `main` / PR #41 pose packing.
2. Keep PR [#68](https://github.com/perielad2-netizen/FashionRise/pull/68) **DRAFT** until a separate explicit merge/deploy authorization says otherwise. Do **not** merge it into `main` as a shortcut.
3. FE stays `a740a9b7` for this BE-only cutover (V1 Studio clients remain compatible; V2 guards stay dormant until Stage D).
4. Alembic stays `005`. No DB migrate / down.
5. No Nginx, Cloudflare, registration, Magic UI, rear artwork, or Stage C/D work in this release.
6. No paid AI / Magic polish enqueue as a smoke test.
7. Preplanned rollback target is exactly `12f7acdff9133e810c0d670697d1500e860f39d6`.

## What ships (when authorized)

Backend `design_service` persistence safety only:

- `draft.v2` / `saved_design.v2` fingerprint (schema, `activeSide`, absent≠empty Back)
- Reject-on-downgrade / Back-strip / clear-without-intent before create/retry shortcuts
- Explicit `clearBackIntent` for emptying Back
- Bidirectional Studio↔saved kind integrity (409 conversion; 422 mixed create)
- Saved create serialized with owner-scoped `pg_advisory_xact_lock`
- Unknown versioned schema family → 422; full saved envelope fingerprint

AI worker code paths are unchanged vs `12f7acdf` for Stage B logic; if the host deploys a single API+worker tree, both processes must still pin to the candidate SHA and remain restartable back to `12f7acdf`.

## Offline verification already recorded (candidate tip)

| Gate | Result (agent-reported; CI check-runs: none) |
|---|---|
| Focused Stage B suite | **32 passed** |
| Full backend pytest | **389 passed** |
| Ruff / Mypy | No new Stage B findings (pre-existing handoff UP017/UP012; `local.py` Path/`None`) |
| Alembic heads | `005 (head)` |

GitHub reported **zero** PR-triggered workflow runs / commit statuses for this HEAD at PM review time. Treat offline pytest as the current gate unless CI is later wired.

---

## Preflight checklist (read-only — run before any authorized cutover)

Complete every item and record evidence. **Stop** on any FAIL.

### A. Identity & isolation

- [ ] `git rev-parse` on the deploy artifact equals `6b253cb52beb9524f976ba805049bf3de2506985`
- [ ] `git merge-base --is-ancestor 12f7acdff9133e810c0d670697d1500e860f39d6 <candidate>` succeeds
- [ ] `git log --oneline 12f7acdf..6b253cb5` lists only the five Stage B commits (no PR #41 / packing)
- [ ] `git diff --name-only 12f7acdf...6b253cb5` is limited to the allowlisted paths above (+ this plan if included)
- [ ] Confirm live production FE release directory / symlink still `a740a9b7`
- [ ] Confirm live production BE/worker process/revision still `12f7acdf…` (or document any drift before proceeding)
- [ ] Confirm production Alembic current = `005`

### B. Host readiness (FashionRise-scoped, no writes yet)

- [ ] Disk / backup target writable under the usual FashionRise backup root
- [ ] `fashionrise-api` and `fashionrise-ai-worker` unit files / env paths identified
- [ ] AI queue has **0** non-terminal jobs (or operator accepts drain plan)
- [ ] No concurrent maint deploy in progress

### C. Backup plan (prepare commands; execute only after deploy auth)

- [ ] Backup API tree + worker tree + env/unit files labeled with pre-change SHA `12f7acdf`
- [ ] Backup note records FE left at `a740a9b7` and Alembic `005`
- [ ] Rollback procedure below is copied into the deploy record

### D. Smoke plan (synthetic / no paid AI)

- [ ] V1 front-only draft create + identical retry (idempotent)
- [ ] V1 front-only OCC update (happy path + stale 409)
- [ ] Synthetic V2 fixture with Back: old-client V1 strip attempt → **409**, stored Back unchanged
- [ ] Metadata-only Studio `designKind=saved_design` → **409** `studio_kind_conversion`
- [ ] Saved design content PUT still immutable; title-only still allowed if currently supported
- [ ] `/health` + `/ready` after restart

---

## Authorized cutover sequence (DO NOT EXECUTE NOW)

Requires a **separate explicit** operator/PM deploy authorization naming SHA `6b253cb5`.

1. Re-run preflight A–D; abort on drift.
2. Take backups (section C).
3. Install API (+ worker tree if co-deployed) at exact `6b253cb5`.
4. Restart `fashionrise-api` (and worker only if its tree was updated); **do not** run Alembic.
5. Confirm process revision = `6b253cb5`; FE still `a740a9b7`; Alembic still `005`.
6. Execute synthetic smoke (section D). No Magic polish / paid OpenAI.
7. Record deploy outcome + backup paths in the usual deploy record / status page.
8. Only after a later independent authorization: Stage C rear artwork, then Stage D FE dual-reader.

## Rollback (preplanned)

1. Restore API (+ worker) tree to exact `12f7acdff9133e810c0d670697d1500e860f39d6`.
2. Restart `fashionrise-api` (+ worker if rolled back).
3. Confirm `/health` + `/ready` and process revision = `12f7acdf…`.
4. No DB migrate down (schema unchanged).
5. FE remains `a740a9b7` (no FE rollback required for this BE-only change).

## Explicit non-goals

- Merge PR #68 into `main`
- Deploy from `main` / PR #41
- FE switch, Nginx, Cloudflare, registration flags
- Alembic revision, data backfill, design rewrite
- Stage C rear PNG generation/approval
- Stage D Front/Back Studio UI
- Paid AI / production Magic validation

## STOP

This plan is **planning only**. Next required human decision: explicit authorization to execute the cutover at SHA `6b253cb5` (or HOLD). Until then: **no merge, no ready-for-review, no deploy, no service restart, no production writes.**
