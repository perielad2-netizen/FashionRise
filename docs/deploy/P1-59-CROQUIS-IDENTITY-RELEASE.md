# P1 #59 — Selected croquis identity — future release plan

**Status:** Draft code only. **Do not deploy** until Technical PM authorization + operator visual acceptance on Issue [#59](https://github.com/perielad2-netizen/FashionRise/issues/59).

**Cursor paid AI this change:** **0**. No production deploy, no merge of PR [#57](https://github.com/perielad2-netizen/FashionRise/pull/57) into `main`, no DB / Nginx / Cloudflare / Sunburst quality changes.

## Production baseline (reverified 2026-10-25)

| Layer | Revision | Notes |
|---|---|---|
| GitHub `main` | `c6fc1eb8b7eac4a2387dadd3b3e1c858d75a3b83` | Includes PR #41 pose-fidelity source (**not** on prod BE) |
| Production frontend | `c6fc1eb8` | Pending independent production re-verification |
| Production backend + AI worker | `b800e53d25dcdf2481f377470543b323798796a7` | Isolated Sunburst maint lineage (P1 #54 / deploy record PR [#58](https://github.com/perielad2-netizen/FashionRise/pull/58)) |
| Alembic | `005` | Unchanged by #59 |
| Image model | `gpt-image-2.5-sunburst` high / 1024×1536 / n=1 / png / `max_retries=0` | Do not alter for this release |

**Hard rules:**
- Do **not** deploy GitHub `main` BE/worker indiscriminately (undeployed PR #41 pose packing).
- Do **not** merge PR #57 into `main` as a shortcut.
- `reference_model_id` is **client-supplied intent metadata**, not a cryptographic proof against sketch pixels.

## Code lineages

| Artifact | Base | Purpose |
|---|---|---|
| Draft PR [#61](https://github.com/perielad2-netizen/FashionRise/pull/61) | `main` @ `c6fc1eb8` | Development / review of FE + full identity contract (may sit atop main pose packing) |
| Maint candidate branch `cursor/p1-59-maint-b800e53d-77c6` | **exactly** `b800e53d` | Audited production-compatible API/worker (+ matching FE if needed) **without** undeployed PR #41 pose packing |

Only the maint candidate is eligible for a future production BE/worker deploy.

## What the patch changes

- Frontend sends canonical `input_data.reference_model_id` (snapshotted with Magic capture).
- Backend validates allowlisted IDs on enqueue; missing metadata compatible; conflicting snake/camel rejected.
- Vision + `images.edit` treat validated selected-reference metadata as authoritative; opposite-family *subject* claims are neutralized across summary / bullets / pose / pose_lock / image_prompt without stripping garment or hairstyle design details.
- No migration, no stored-design rewrite, no remapping of legacy `female`/`male` IDs.

## Backend-first compatibility release sequence (DO NOT EXECUTE NOW)

A production `POST /ai/sketch/polish` **enqueues a job that may trigger paid Sunburst work**. Do **not** use a live polish enqueue as a casual zero-cost smoke test.

1. **Backup** production API/worker trees + env/unit files (and FE release directory).
2. **Deploy BE/API + AI worker only** from the audited maint candidate based on `b800e53d` (after separate Technical PM authorization).
3. **Verify** `/health` + `/ready` (or project-equivalent readiness) and that API/worker process revisions match the candidate tip.
4. **Validate identity contract without paid work:**
   - Prefer offline/staging enqueue against the new binary, **or**
   - Production-safe checks that cannot start the worker (e.g. `AI_WORKER_ENABLED=false` already true for API; ensure standalone worker is stopped / Magic temporarily gated before any polish POST), **or**
   - Exercise only non-enqueue validation paths if available.
   - Confirm invalid `reference_model_id` → 422 and missing metadata still accepted **without** creating a billable completed image.
5. **Deploy the corresponding frontend** patch only after BE compatibility is established (old FE → new BE remains safe because missing `reference_model_id` is compatible; new FE → old BE is **not** identity-safe).
6. **Operator visual acceptance** only under separately authorized testing (male→male and female→female croquis fidelity, pose + garment preservation).

### Controlled Magic gate (if the compatibility window cannot be closed atomically)

If FE and BE cannot be cut over without a window where new FE hits old BE:

- Temporarily disable Magic UI (`VITE_MAGIC_UI_ENABLED=false` rebuild) **or** stop the AI worker and show an honest Studio notice before FE cutover.
- Restore Magic only after BE identity patch is live and readiness checks pass.
- Document the gate window in the deploy record.

## Rollback

1. Restore previous FE release directory / symlink (pre-#59 FE).
2. Restore previous BE/worker tree at `b800e53d` (or the pre-candidate tip).
3. Restart `fashionrise-api` + `fashionrise-ai-worker`.
4. No DB rollback (no schema change). Jobs without `reference_model_id` remain valid.
5. If Magic was gated, restore the prior Magic UI / worker run state from backup.

## Visual acceptance gate (operator)

Acceptance is **not** “Magic returns an image.” For a male library croquis (e.g. `male-straight`) with the operator’s grey top + blue trousers sketch:

- Result remains recognizably the selected **male** fashion-croquis family.
- Pose / stance / limb relationships remain recognizable.
- Garment colors, silhouette, and sketch-supported details (including hairstyle/garment choices) remain faithful.
- No silent swap to a female-presenting runway figure.

Keep Issue #59 **open** until that gate passes.
