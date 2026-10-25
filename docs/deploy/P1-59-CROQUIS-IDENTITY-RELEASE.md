# P1 #59 — Selected croquis identity — future release plan

**Status:** Offline release-readiness complete for Technical PM decision. **Do not deploy** until authorization + operator visual acceptance on Issue [#59](https://github.com/perielad2-netizen/FashionRise/issues/59).

**Cursor paid AI this change:** **0**. No production deploy, no merge of PR [#57](https://github.com/perielad2-netizen/FashionRise/pull/57) into `main`, no DB / Nginx / Cloudflare / Sunburst quality changes.

## Verified SHAs (2026-10-25)

| Artifact | SHA |
|---|---|
| GitHub `main` | `c6fc1eb8b7eac4a2387dadd3b3e1c858d75a3b83` |
| Draft PR [#61](https://github.com/perielad2-netizen/FashionRise/pull/61) head | branch tip (includes test-only branch-guard fix + release-gate docs; FE + BE on `main`) |
| Production FE (last reported) | `c6fc1eb8` |
| Production BE/worker (last reported) | `b800e53d25dcdf2481f377470543b323798796a7` |
| Maint candidate `cursor/p1-59-maint-b800e53d-77c6` | `dafe56513317a6f890e9045e8f32a228ad25f17a` (docs sync atop runtime `1450b5a1`) |
| Alembic | `005` (unchanged) |
| Image model | `gpt-image-2.5-sunburst` high / 1024×1536 / n=1 / png / `max_retries=0` |

**Hard rules:**
- Do **not** deploy GitHub `main` BE/worker indiscriminately (undeployed PR #41 pose packing is on `main`).
- Deploy BE/worker **only** from the maint candidate based on `b800e53d`.
- Do **not** merge PR #57 into `main` as a shortcut.
- `reference_model_id` is **client-supplied intent metadata**, not a cryptographic proof against sketch pixels.
- Do **not** enqueue a production Magic polish job as a zero-cost smoke test.

## Code lineages

| Artifact | Base | Purpose |
|---|---|---|
| Draft PR [#61](https://github.com/perielad2-netizen/FashionRise/pull/61) | `main` @ `c6fc1eb8` | Development / review of FE + full identity contract (sits atop main, including undeployed PR #41 source) |
| Maint candidate `cursor/p1-59-maint-b800e53d-77c6` @ `dafe5651` | **exactly** `b800e53d` | Production-compatible API/worker **without** PR #41 pose packing (docs tip; runtime identity since `1450b5a1`) |

Only the maint candidate is eligible for a future production BE/worker deploy. FE from PR #61 after BE is live.

## What the patch changes

- Frontend sends canonical `input_data.reference_model_id` (snapshotted with Magic capture before async work).
- Backend validates allowlisted IDs on enqueue; missing metadata compatible; conflicting snake/camel rejected.
- Vision + `images.edit` treat validated selected-reference metadata as authoritative; opposite-family *subject* claims are neutralized across summary / bullets / pose / pose_lock / image_prompt without stripping garment or hairstyle design details.
- Professional fashion-illustration prompt frame retained; no new model/pose/`images.generate` fallback.
- No migration, no stored-design rewrite, no remapping of legacy `female`/`male` IDs.

## Offline verification (release gate)

### Branch-guard discrepancy (resolved)

| Check | Result |
|---|---|
| Unmodified `main` @ `c6fc1eb8` | **1 failed** / 265 passed — `test_cli_default_is_dry_run` (expects ancient branch `cursor/openai-gpt6-luna-77c6`) |
| Disposition | **Genuinely pre-existing** on exact unmodified main |
| PR #61 fix | Test-only: stub `verify_repo_state` in that offline dry-run test (no runtime harness change) |
| Maint tip | Already had an equivalent stub; full suite green without further change |

### Full suites

| Surface | Result |
|---|---|
| PR #61 backend pytest | **310 passed** |
| Maint `1450b5a1` / tip `dafe5651` backend pytest | **331 passed** (re-run at `1450b5a1` runtime tip; docs-only commit after) |
| PR #61 frontend Vitest | **379 passed** (72 files) |
| PR #61 `tsc -b` / oxlint / `build` / `check:sw` | **PASS** (`sw_access_safety ok=true`); oxlint warnings pre-existing |
| Ruff / mypy | Baseline noise only (main ruff 107 / mypy 8; PR #61 same counts; scoped BLE001 on `sketch_openai` also on main) |
| GitHub Actions at PR/maint heads | **None configured / zero check-runs** |
| Paid AI | **0** |

### Identity contract (mocked)

- 10 built-in croquis IDs + legacy `male`/`female` + `custom`/`blank`
- Conflicting snake_case/camelCase rejected
- Async `useStudioEditor` capture preserves pre-capture model id across mid-flight model switch
- Both AI stages preserve selected-croquis intent; contradictory vision subject claims neutralized without destroying garment/hairstyle details
- No unauthorized model / pose / `images.generate` fallback

## Backend-first compatibility release sequence (DO NOT EXECUTE NOW)

A production `POST /ai/sketch/polish` **enqueues a job that may trigger paid Sunburst work**. Do **not** use a live polish enqueue as a casual smoke test.

1. **Preflight (read-only):** confirm live prod FE/BE/worker SHAs, Alembic `005`, `OPENAI_IMAGE_MODEL=gpt-image-2.5-sunburst`, worker `max_retries=0`, AI queue has **0** non-terminal jobs.
2. **Backup** production API/worker trees + env/unit files (and FE release directory).
3. **Deploy BE/API + AI worker only** from maint tip `dafe5651` (runtime identity identical to `1450b5a1`; docs-only atop), after Technical PM authorization.
4. **Verify** `/health` + `/ready` (or project-equivalent) and that API/worker process revisions match the candidate tip.
5. **Compatibility window (safe, no paid work):**
   - Old FE → new BE: safe (missing `reference_model_id` accepted).
   - New FE → old BE: **not** identity-safe — do not ship FE first.
   - Prefer offline/staging validation of 422 on invalid ids + accept missing metadata **without** completing a billable image.
   - If needed: keep worker stopped / Magic UI gated (`VITE_MAGIC_UI_ENABLED=false`) until BE tip is confirmed, then restore.
6. **Deploy FE** from the authorized PR #61 frontend revision only after BE compatibility is established.
7. **Operator visual acceptance** only under **separately authorized** paid testing (see below). Keep Issue #59 **OPEN** until that gate passes.

### Controlled Magic gate (if the window cannot be closed atomically)

- Temporarily disable Magic UI or stop the AI worker and show an honest Studio notice before FE cutover.
- Restore Magic only after BE identity patch is live and readiness checks pass.
- Document the gate window in the deploy record.

## Rollback

1. Restore previous FE release directory / symlink (pre-#59 FE).
2. Restore previous BE/worker tree at `b800e53d` (or the pre-candidate tip).
3. Restart `fashionrise-api` + `fashionrise-ai-worker`.
4. No DB rollback (no schema change). Jobs without `reference_model_id` remain valid.
5. If Magic was gated, restore the prior Magic UI / worker run state from backup.

## Operator acceptance procedure (future — separate paid authorization)

**Requires separate PM authorization before any paid OpenAI call.** Estimate: 2 polish jobs (male + female) under Sunburst high.

| # | Setup | Pass criteria |
|---|---|---|
| 1 | Select a **male** library croquis (e.g. `male-straight`). Sketch a simple garment (document colors/silhouette). Run Magic polish. | Look remains **male-presenting**; pose/body proportions recognizable vs croquis; garment silhouette/colors/textiles faithful; professional fashion-illustration style retained — not a female runway swap. |
| 2 | Select a **female** library croquis (e.g. `female-straight` or `female-hand-hip`). Sketch a distinct garment. Run Magic polish. | Look remains **female-presenting**; pose/body proportions recognizable; garment fidelity + illustration style as above. |

Fail closed on silent opposite-family swap, major repose, or loss of sketched garment identity. Metadata/prompt tests are **not** a substitute for this visual gate.
