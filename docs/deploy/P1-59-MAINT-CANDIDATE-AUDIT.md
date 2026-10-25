# P1 #59 — Production maint candidate audit (`b800e53d`)

**Branch:** `cursor/p1-59-maint-b800e53d-77c6`  
**Base:** `b800e53d25dcdf2481f377470543b323798796a7` (exact production BE/worker tip)  
**Purpose:** Offline, auditable API/worker patch for Issue #59 **without** undeployed PR #41 pose packing.

## Provenance checks

| Check | Result |
|---|---|
| Base SHA | `b800e53d25dcdf2481f377470543b323798796a7` |
| PR #41 (`4819b951`) ancestor of this tip? | **No** |
| `pose_lock` / `_POSE_LOCK_*` / priority evidence packing present? | **No** (only a comment that packing is excluded) |
| Image model / quality / Alembic changed? | **No** |
| Database migration? | **No** |

## Scope (expected files)

- `backend/app/services/reference_croquis.py` (new)
- `backend/app/services/ai_service.py` (enqueue validation only)
- `backend/app/services/sketch_openai.py` (identity in vision user text + edit brief; subject neutralization; `job=` into `_build_image_prompt`)
- `backend/tests/test_reference_croquis_identity.py` (new)
- `docs/deploy/P1-59-MAINT-CANDIDATE-AUDIT.md` (this file)
- `docs/deploy/P1-59-CROQUIS-IDENTITY-RELEASE.md` (backend-first plan)

Frontend Magic contract lives on draft PR #61 (`main`-based). Deploy FE only **after** this BE candidate is live.

## Diff policy

`git diff b800e53d...HEAD` must show only the files above (plus docs). No wholesale replacement of the production edit-prompt frame with main’s pose-lock packer.

## Verification (offline)

See commit message / STOP report for exact pytest/ruff/mypy counts on this tip.
