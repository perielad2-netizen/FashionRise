# P1 #54 — Production maintenance isolation plan (offline)

**Status:** Prepared for Technical PM review. **Not authorized for deploy.**  
**Production BE/worker SHA:** `2cbc1ad04e5bfc01d1d356c92398e26e3014afe9`  
**Production FE SHA (unchanged by this plan):** `c6fc1eb8b7eac4a2387dadd3b3e1c858d75a3b83`  
**Alembic:** `005` (no migration in this plan)

## Goal

Ship **only**:

1. Observability hardening from PR #55 (allowlisted diagnostics), and  
2. Image-model migration to `gpt-image-2.5-sunburst`,

onto the **currently deployed** backend/worker revision — **without** undeployed Magic pose-fidelity PR #41 from `main`.

## Why isolation is required

| Ref | Contents |
|-----|----------|
| Prod BE/worker | `2cbc1ad0` = WEB-V4E Magic quality era |
| GitHub `main` | Includes PR #41 pose-fidelity + later FE merges; BE pose changes **not** production-validated |
| Risk of deploying `main` BE | Introduces unauthorized pose-prompt behavior alongside the model fix |

## Offline maintenance branch (candidate)

| Field | Value |
|-------|-------|
| Branch name | `cursor/magic-maint-2cbc1ad0-54-77c6` |
| Base | `2cbc1ad04e5bfc01d1d356c92398e26e3014afe9` |
| Intended contents | Cherry-picked / ported observability + Sunburst migration only |
| Deploy | **Forbidden** until separate PM authorization |

### Required verification before any future authorize

1. `git log --oneline 2cbc1ad0..HEAD` lists only approved maintenance commits.  
2. `git diff --stat 2cbc1ad0...HEAD` limited to expected paths (see below).  
3. `git diff 2cbc1ad0...HEAD -- backend/app/services/sketch_openai.py` reviewed file-by-file for pose-fidelity hunks — **must be absent**.  
4. Full backend pytest on the maintenance branch (mocked).  
5. Confirm production `.env` change plan: `OPENAI_IMAGE_MODEL=gpt-image-2.5-sunburst` + `OPENAI_IMAGE_QUALITY=high` only after code deploy readiness.  
6. Forward-port: merge/rebase equivalent changes onto `main` so main stays consistent (observability PR #55 + migration PR), without implying prod deploy of #41.

### Expected touch paths (allowlist)

- `backend/app/services/sketch_openai.py` (capabilities + retired fail-closed + Sunburst kwargs; observability allowlists if ported)
- `backend/app/services/ai_worker.py` / `ai_service.py` / `schemas/ai.py` (observability only)
- `backend/app/core/config.py` (defaults)
- `backend/tests/**` related
- `backend/.env.example`, `deploy/env.production.example`
- `docs/incidents/**`, `docs/00-PROJECT-STATUS.md`
- `backend/README.md` / `docs/OPENAI_MODEL_MIGRATION.md` as needed

### Explicitly excluded

- Pose-fidelity-only prompt packing changes from PR #41 not already in `2cbc1ad0`
- Frontend / Nginx / Cloudflare / Alembic / DB writes
- Unrelated VPS services and untracked host files

## Rollback

1. Restore previous backend/worker executable tree / git checkout at `2cbc1ad0` (or prior release tarball under `/var/backups/fashionrise/`).  
2. Restore previous `OPENAI_IMAGE_MODEL` / quality env values from the pre-change env backup.  
3. Restart only `fashionrise-api` + `fashionrise-ai-worker` if a future authorized deploy had restarted them.  
4. Confirm `/health` + `/ready`; no FE switch required for BE-only rollback.

## Dependency compatibility

- Keep `openai>=1.109.1,<2.0.0` unless a later authorized SDK bump is reviewed.  
- Sunburst model id is passed as `str` (SDK accepts it).  
- No DB schema change.

## STOP

This document and any offline maintenance branch are **not** a deploy approval. Next PM decision selects exact commits, authorizes config change, and optionally one budgeted Magic validation.
