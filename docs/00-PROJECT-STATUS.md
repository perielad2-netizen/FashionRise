# FashionRise — project status & session handoff

**Purpose:** Single page to align **new chat sessions** and humans on **what exists**, **where it lives**, and **what to do next**.  
**Maintenance:** After each meaningful milestone, update the **last updated** line, **milestone table**, and **suggested next steps**. Touch **`docs/06-implementation-phases.md`** when phase checkboxes move.

**Last updated:** 2026-09-14 (Magic uses sketch **image edit** for fidelity; +3 poses = 8 croquis)

**Source repo:** [github.com/perielad2-netizen/FashionRise](https://github.com/perielad2-netizen/FashionRise) (default branch **`main`**). Root **`.gitignore`** excludes `backend/.env`, Unity `Library/` / `Logs/` / `UserSettings/`, etc.

---

## Session pause — where we stopped (read this first in a new chat)

**Paused:** 2026-09-07 evening. **Resume here next session.**

### What works now

- Local API on **port 8001** (`http://127.0.0.1:8001/api/v1`). Unity **FashionRise_UI → FashionRise App → Api Config → Base Url** must match.
- Account: **`perielad@gmail.com`** / **`NoaPeri`** (reset via `backend/scripts/set_user_password.py` if needed).
- Kid loop: Girl/Boy (+ pose croquis) → sketch → **Magic** → **Your look** shows **generated AI image** (not only text) + Share.
- OpenAI: vision polish uses **`gpt-4o-mini`**; look image uses **`gpt-image-1`** (~1 min, b64 → local storage → static URL). Account has **no dall-e-3**.
- Verified in Play mode: emerald gown image on **Your look** with Source OpenAI metadata.

### Product note (Magic style)

**2026-09-14 night:** Magic look generation now prefers OpenAI **`images.edit`** with the child's sketch bytes + `input_fidelity=high` (text-only `images.generate` is fallback only). This is the core fidelity fix — earlier results looked “pretty” but unrelated because they were invented from text. Croquis poses expanded to **8** (Stand/Walk/Show/Hip/Turn/Arms/Side/Back); run `tools/generate_extra_croquis.py` if `female_06..08` / `male_06..08` missing. **Restart API** after pull.

### Shipped this session (tech)

| Area | Change |
|------|--------|
| Unity sketch UX | Aspect-fit pad, white paper, remember-me login, pose library (`female_01..05`, `male_01..05`) under `Resources/SketchReference/` |
| Backend Magic image | After `sketch_polish` vision JSON, generate image, save via `LocalStorageBackend`, set `result_data.image_url` |
| Config | `OPENAI_IMAGE_*` in `.env` / `.env.example`; `PUBLIC_UPLOAD_BASE_URL=http://127.0.0.1:8001/static/uploads`; **storage root resolves under `backend/`** (not cwd) in `config.py` |
| Unity Your look | `ConceptResultScreen` loads `image_url` (refetch from job); rewrites `localhost` → API host; caches PNG for Share |
| Fallbacks | Image models: `gpt-image-1` → `gpt-image-1-mini` → `dall-e-2`; set `OPENAI_IMAGE_MODEL=off` to disable |

### Dev gotchas (don’t re-debug blindly)

1. Start API from **`backend/`** (or rely on absolute storage resolve after restart). Relative `./data/storage` used to write to repo-root when cwd was wrong → static **404**.
2. `gpt-image-1` is **slow** (~45–60s after chat/completions). Wait for log: `stored look image`.
3. Images API: no `response_format` param; often **b64 only** (no URL).
4. Unity must wait for job **completed** (includes image gen) before navigating; **See last result** now re-fetches `image_url`.

### Suggested order for the *next* session

1. **Play-test Magic** after API restart — if still too photoreal, add sketch-as-reference via Images edit API.  
2. **Kid loop polish** — empty/error copy; optional big brush-only kid toolbar.  
3. **Viral share v2** — stronger caption + one-tap gallery publish; then AI share-video spike.  
4. **Pro door** — leave atelier under More… until viral loop feels great.

### Product vision (locked)

- **Front door (kids ~7–8+):** Girl/Boy → draw → AI Magic → share (later: **AI video**). Premium, not a dumb dress-up toy.
- **Talent path:** gallery, challenges, discovery (Prompt 7).
- **Pro depth:** fabrics, atelier, ratings, handoff — behind **More…** / Guided↔Pro.

**Parking lot:** full AI worker split at scale, WebGL polish, `POST /auth/logout`, admin moderation UI, audit logs, vector ink.

---

## Product vision (north star)

FashionRise helps **young creators** (including kids ~7–8+) **draw fashion ideas**, get **AI polish**, and **share** so talent can be **seen** — including going viral. The same app grows with them: **pro tools** and **designer handoff** for people who can make real designs.

- **Simple first session:** Girl/Boy → canvas → Magic → Share.  
- **Serious product underneath:** architecture, moderation-ready backend, atelier, portfolio / handoff (see `docs/all prompts.txt` Prompt 0 + Prompt 7 talent discovery).  
- **Principle:** One codebase. Kid-simple chrome by default; Pro depth available — not two apps.

---

## Roadmap pillars (execution order)

| Pillar | Outcome | Ties to |
|--------|---------|--------|
| **A — Sketch & authoring** | **Kid loop live** + **AI look image on Your look**. Next: image **closer to sketch** (less photoreal), kid toolbar polish, later vector/layers | Prompt 6, Phase 5b |
| **B — Social & growth / virality** | Gallery/ratings/follows exist; front door Share works. Next: one-tap publish from Magic result, challenges, **AI share video** | Phase 4–5b, Prompt 7 discovery |
| **C — Maker handoff** | Spec/PDF placeholder shipped for **pro** path. Next when talent needs it | Prompt 7 / Phase 6 |
| **D — Trust & scale** | Hardening, moderation, CI | Phase 7 + Prompt 8 |

Work **front door first**; keep Pro behind More… until the viral loop feels great.

---

## Current state (executive)

| Area | Status | Location |
|------|--------|----------|
| **Backend API** | Implemented (FastAPI, JWT + refresh, CRUD, uploads, gallery social + follows, AI jobs — **OpenAI vision** when keys + worker configured, else stub) | `backend/app/` |
| **Database** | PostgreSQL + Alembic **`001`–`003`**; downgrades use **`if_exists`** for recovery on stamped-but-empty DBs | `backend/alembic/versions/` |
| **Unity client** | **Kid front door** on Home; sketch + Magic + Share; atelier/gallery/profile under More…; API mode default | `FashionRise/Assets/FashionRise/` |
| **Deployment** | Ubuntu + systemd + Nginx + Postgres scripts & guide | `deploy/` |
| **Docs** | Architecture, API, DB, Unity, phases — this folder; master prompts in **`all prompts.txt`** | `docs/` |

---

## Milestone tracker (prompts / major deliveries)

| Milestone | Status | Notes |
|-----------|--------|--------|
| Backend foundation (models, routes, auth, seed, Alembic) | **Done** | See `docs/03-backend.md`, `05-api.md` |
| Unity ↔ FastAPI (dual mode, *ApiService* stack) | **Done** | `docs/unity-backend-integration.md`, `unity-services.md` |
| Production deploy (Ubuntu, Nginx, Postgres) | **Done** | `deploy/README_DEPLOYMENT.md` |
| V2 Prompt 6 (sketch AI routes, gallery likes/comments/sort, extended categories) | **In progress** | Kid UX + **AI image on Your look** (2026-09-07); next: sketch-faithful image style + viral share/video |
| Hardening (SlowAPI rate limits on auth/uploads/AI; `/auth/logout`, admin, WebGL polish) | **Partial** — **rate limits** shipped (`backend/app/core/rate_limit.py`); logout/admin/WebGL TBD |

### Original prompt series (from `docs/all prompts.txt`)

| # | Intent | Reality check |
|---|--------|----------------|
| **0** | Master context / quality bar | Living — premium + talent discovery; **front door simplified for kids** without becoming a toy dress-up app |
| **1** | Full architecture | **Done** (living docs in `docs/`). |
| **2** | Unity client V1 | **Done** (screens, mocks, services). |
| **3** | FastAPI backend V1 | **Done**. |
| **4** | Connect Unity ↔ backend | **Done** (API mode, auth, screens). |
| **5** | Production deploy | **Done** (`deploy/`). |
| **6** | V2: sketch AI, social, richer catalog, UX polish | **In progress** — tech + **kid front door**; viral image/video share next |
| **7** | V3 / pro platform (handoff, challenges, talent score, …) | **Partial** — handoff/reputation slices; challenges / AI video not started |
| **8** | Final architecture / quality **review** | **Not started** |

---

## Repository map

```text
FashionRise/
├── backend/                 # FastAPI app (Python 3.11+)
│   ├── app/                 # main, core, api, models, services, storage, …
│   ├── alembic/
│   ├── tests/
│   ├── requirements.txt
│   └── README.md
├── deploy/                  # Production: systemd, nginx, setup/update/backup scripts
├── docs/                    # This documentation set (+ 00-PROJECT-STATUS.md, all prompts.txt)
└── FashionRise/             # Unity project
    └── Assets/FashionRise/  # Game code (see README_Unity.md)
```

---

## Configuration quick reference

| Concern | Dev | Production |
|--------|-----|------------|
| Backend env | `backend/.env` from `.env.example` | `deploy/env.production.example` → server `.env` |
| CORS | `*` allowed in non-production | Explicit origins; `*` **rejected** when `ENVIRONMENT=production` |
| Unity API mode | `FashionRiseApp` → Api Config (**default:** API on, local URL) | Same + HTTPS base URL; **phone:** LAN IP + CORS |
| One-click API preset (Editor) | **FashionRise → Use Local API (127.0.0.1:8001) — apply to scene** | N/A |

---

## When you open Cursor next (start here)

1. Read **this file** through **Suggested next steps** (below).
2. **Pull** latest if you work from another machine: `git pull origin main`.
3. **Backend:** `cd backend`, activate venv, ensure **`backend/.env`** exists — Postgres running, **`alembic upgrade head`**, uvicorn. Password reset: `python scripts/set_user_password.py email "password"`.
4. **Unity:** open `FashionRise/`, scene **App**, Play — expect **Girl/Boy** home, not atelier-first. API at `http://127.0.0.1:8001/api/v1`.
5. Pick work from **Suggested next steps**; after a milestone, update **Last updated** + **Changelog** here.

---

## Suggested next steps (aligned with full product)

1. **Kid loop polish** — Play-mode pass; optional kid-simple brush row; show AI result **image** on Your look.  
2. **Virality** — one-tap publish + share from Magic result; then **AI video** share spike.  
3. **Talent / Pro** — challenges + discovery (Prompt 7); handoff PDF quality when needed.  
4. **Engineering** — CI `pytest`; secure token storage on mobile.  
5. **Prompt 8** before a public 1.0 narrative.

_Update this list as pillars complete._

---

## Doc index (what to read when)

| Question | Doc |
|----------|-----|
| What is the system? | `01-architecture-overview.md` |
| Original prompts? | `all prompts.txt` |
| What’s implemented in Unity? | `02-unity-client.md`, `unity-services.md`, `unity-backend-integration.md` |
| What’s implemented in the API? | `05-api.md`, `03-backend.md` |
| DB tables? | `04-database.md` (+ **models** as source of truth) |
| Phase checklist? | `06-implementation-phases.md` |
| How to deploy? | `../deploy/README_DEPLOYMENT.md` |
| **Session handoff?** | **`00-PROJECT-STATUS.md` (this file)** |

---

## Changelog (handoff doc only)

| Date | Summary |
|------|---------|
| 2026-09-07 | **Vision reframe:** kid front door + talent/pro depth; Unity Home/Sketch/Magic/Result/Share + splash; `SketchNavContext`; `TryShareImageFile`. |
| 2026-05-13 | **Session handoff refresh:** dual-layer sketch + `SketchReference` PNGs + `OnShown` bootstrap + `SketchFigurePreferences`; **auth** email lower + password trim + `scripts/set_user_password.py`; Unity **GUID** / **asmdef** fixes. |
| 2026-05-12 | **Unity iOS:** Photos import for sketch `Imports`. |
| 2026-05-11 | **Session pause doc sweep** + reputation v1 + gallery/social + handoff slice + migration recovery. |
| 2026-05-10 | Added handoff doc; GitHub push; Prompt 6 / pillars. |
