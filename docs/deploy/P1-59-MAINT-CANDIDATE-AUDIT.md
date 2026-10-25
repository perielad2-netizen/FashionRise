# P1 #59 — Production maint candidate audit (`b800e53d`)

**Branch:** `cursor/p1-59-maint-b800e53d-77c6`  
**Base:** `b800e53d25dcdf2481f377470543b323798796a7` (exact production BE/worker tip)  
**Head:** `1450b5a1d0b472058b47247d9d74133c7abd9c72`  
**Purpose:** Offline, auditable API/worker patch for Issue #59 **without** undeployed PR #41 pose packing.

## Provenance checks (reverified 2026-10-25)

| Check | Result |
|---|---|
| `git merge-base --is-ancestor b800e53d HEAD` | **Yes** |
| Commits ahead of `b800e53d` | **2** (zero behind) |
| PR #41 (`4819b951`) ancestor of this tip? | **No** |
| `pose_lock` / `_POSE_LOCK_*` / priority evidence packing present? | **No** (comment only that packing is excluded) |
| Image model / quality / Alembic changed? | **No** — still `gpt-image-2.5-sunburst` high, `max_retries=0`, no `images.generate` |
| Database migration / Nginx / Cloudflare / Front-Back? | **No** |

## File-level release diff (`b800e53d...1450b5a1`)

| Path | Role |
|---|---|
| `backend/app/services/reference_croquis.py` | **New** — allowlist + parse + snake/camel conflict |
| `backend/app/services/ai_service.py` | Enqueue validation only (+5 lines) |
| `backend/app/services/sketch_openai.py` | Identity in vision user text + edit brief; subject neutralization |
| `backend/tests/test_reference_croquis_identity.py` | **New** — offline mocks |
| `docs/deploy/P1-59-CROQUIS-IDENTITY-RELEASE.md` | Backend-first plan |
| `docs/deploy/P1-59-MAINT-CANDIDATE-AUDIT.md` | This audit |

No frontend in the maint tip. FE ships from draft PR #61 **after** BE is live.

## Offline verification (this tip)

| Check | Result |
|---|---|
| Full backend pytest | **331 passed** |
| Branch-guard dry-run test | Already branch-independent on this tip (stub); suite green |
| Ruff `app tests` | **108** findings — baseline noise (same class as `main` 107); not introduced as a #59 regression gate |
| mypy `app` | **8** errors in 5 files — identical baseline set (`jose`/`passlib` stubs, `local.py`, `seed.py`, `main.py` rate-limit handler) |
| Paid OpenAI / live polish enqueue | **0** / not run |

## Diff policy

`git diff b800e53d...HEAD` must show only the files above. No wholesale replacement of the production edit-prompt frame with main’s pose-lock packer.
