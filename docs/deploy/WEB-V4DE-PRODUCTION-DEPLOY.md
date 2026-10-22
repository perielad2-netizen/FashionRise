# WEB-V4D + WEB-V4E production deploy record

**When (UTC):** 2026-10-22 ~20:42–20:45Z  
**Authorized GitHub `main` SHA:** `2cbc1ad04e5bfc01d1d356c92398e26e3014afe9`  
**Authorization:** Operator comment on merged PR #35 (deploy approved; paid Magic **not** approved).

## Before → after

| Component | Before | After |
|-----------|--------|-------|
| GitHub `main` | `3376827c` (V4D merged) / prior BE `c21fee6b` | `2cbc1ad0` |
| Backend (`/opt/fashionrise/src`) | `c21fee6b` | `2cbc1ad0` |
| `fashionrise-api` | active @ prior | active @ `2cbc1ad0` |
| `fashionrise-ai-worker` | active @ prior | active @ `2cbc1ad0` |
| Frontend Nginx root | `/var/www/fashionrise/releases/d7e37b59` | `/var/www/fashionrise/releases/2cbc1ad0` |
| Alembic | `005` | `005` (unchanged; no upgrade) |

## Backup / rollback

Path: `/var/backups/fashionrise/v4de-deploy-20261022T204254Z`

- `fashionrise_beta.sql.gz` — **1,520,125** bytes, `gzip -t` OK  
- Nginx + systemd units + prior `sketch_openai.py` + `.env` sha256 + `ROLLBACK.md`  
- Prefer **app rollback** (git `c21fee6b` + FE `d7e37b59`) over DB restore  

## Controls verified

- AI jobs before worker restart: **0** queued/running (`completed=9`)  
- `OPENAI_MODEL=gpt-6-luna`, `OPENAI_IMAGE_MODEL=gpt-image-1` unchanged  
- Live import: `with_options(max_retries=0)` present; no `images.generate(` / mini fanout  
- `.env` sha256 unchanged across checkout  
- Neighbor listeners `:8000/:8001/:8002` still present; FashionRise remains `:8010`  
- Nginx FashionRise allowlists unchanged (AI polish/jobs, fabrics, register POST-only)  
- Cloudflare Access / AOP config not modified  

## Frontend build gates (on VPS)

| Check | Result |
|-------|--------|
| `npm test` | **278 / 278** |
| `npm run lint` | 0 errors (pre-existing warnings) |
| `npm run build` (`tsc -b` + vite) | Pass |
| `check:sw` / installed SW | **ok=true**; no NavigationRoute / HTML precache |
| Legacy croquis in release | `female_model.png`, `male_model_display.png` |
| Library croquis | **10** PNGs under `models/library/` |

## Nonpaid acceptance

**Infrastructure PASS:** health/ready; unauth API 401/422 as expected; services active; worker idle after restart (no OpenAI traffic); deploy paid calls **0**.

**Signed-in Studio browser (operator):** **PENDING** — croquis defaults, legacy geometry, tabs/focus, fills/fabrics, save/autosave/export not claimed without Access session.

**Paid Magic visual retest:** **BLOCKED** until separate operator authorization.

## Next action

1. Operator Access login → Studio UX acceptance for WEB-V4D.  
2. Separately authorize **one** paid Magic generation; score with `docs/WEB-V4E-MAGIC-QUALITY.md`.  
3. Cursor must not initiate paid OpenAI calls.
