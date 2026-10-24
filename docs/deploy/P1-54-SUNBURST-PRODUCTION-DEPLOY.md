# P1 #54 — Sunburst production deploy record

**When (UTC):** 2026-10-24T23:56Z · **Asia/Jerusalem:** 2026-10-25 01:56 IDT  
**Authorization:** Issue #54 operator comment (production Magic recovery)  
**PR #57 merge into main:** **NOT performed**

## Deployed

| Layer | Before | After |
|-------|--------|-------|
| Backend / AI worker | `2cbc1ad0` | **`b800e53d25dcdf2481f377470543b323798796a7`** |
| Frontend | `c6fc1eb8` | **`c6fc1eb8` (unchanged)** |
| Alembic | `005` | **`005` (unchanged)** |
| Nginx / Cloudflare | — | **unchanged** |

## Effective AI image config

- `OPENAI_IMAGE_MODEL=gpt-image-2.5-sunburst`
- `OPENAI_IMAGE_SIZE=1024x1536`
- `OPENAI_IMAGE_QUALITY=high`
- `OPENAI_MODEL=gpt-6-luna` (unchanged)
- `AI_WORKER_ENABLED=false` (standalone worker)

## Verification

- `fashionrise-api` / `fashionrise-ai-worker` **active**
- `/health` ok · `/ready` database ok
- Runtime settings loaded Sunburst / high / 1024x1536
- `pose_lock` absent (PR #41 not deployed)
- AI jobs: 19 completed / 3 failed / **0** non-terminal; no new jobs during deploy
- Cursor autonomous paid OpenAI calls: **0**
- Offline pytest on candidate before deploy: **287 passed**

## Backup / rollback

- Backup: `/var/backups/fashionrise/p1-54-sunburst-deploy-20261024T235606Z`
- Rollback helper: `$BACKUP/ROLLBACK.sh` (restores `2cbc1ad0` + sets `OPENAI_IMAGE_MODEL=off`)
- Restoring retired `gpt-image-1` is **not** a functional Magic recovery

## Operator next step

Manual Magic testing at https://fashionrise.app. Visual acceptance **PENDING**.
