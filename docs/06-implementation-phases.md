# FashionRise — Implementation phases

**Living checklist.** Update checkboxes and notes when work completes. For a **one-page handoff**, see [`00-PROJECT-STATUS.md`](./00-PROJECT-STATUS.md).

---

## Product pillars — full FashionRise (pro + beginners + makers)

_Check these off as slices ship. Same codebase: **Pro** depth, **Guided** mode for approachable UX._

### Pillar A — Serious sketch & authoring

- [x] Raster sketch surface: draw, undo stack, clear, PNG export — `Presentation/Sketch/UiSketchPad.cs`, wired from `SketchCanvasScreen` (`SketchReference` → `file:…` under persistent data)
- [x] Local image import: `persistentDataPath/Sketches` + **`Imports`** (PNG/JPEG), Import screen — **Pipeline** (as-is) vs **Trace** (underlay on `UiSketchPad`)
- [ ] Layers / vectors; **native** OS/gallery picker; export beyond local PNG
- [ ] Autosave / revision snapshots (ties to `design_revisions` + API)
- [ ] AI jobs: background workers or provider integration (replace immediate “noop” completion where needed)
- [ ] Guided vs Pro UI toggle (density, labels, optional tutorials) — **UX**, not a second app

### Pillar B — Share & social proof

- [ ] Publish to gallery from create flow (one-tap path); share link / image card
- [ ] Feed discovery (trending, top rated, follows optional later)
- [ ] Fair reputation model (ratings + quality signals; avoid exploitative “kid game” mechanics)

### Pillar C — Real garment / sewing path

- [ ] Maker handoff package: garment spec summary, materials, measurements placeholders, export downloads
- [ ] Backend `handoff` routes + storage; Unity `IDesignerHandoffService` (or equivalent)
- [ ] Optional: print-friendly / PDF pipeline for atelier or classroom

### Pillar D — Trust & launch readiness

- [ ] Prompt 8 quality review; security pass; moderation admin path; CI and staging

---

## Phase 0 — Foundation

- [x] Repo layout: Unity `FashionRise/Assets/FashionRise/**` (screens, mocks, API adapters)
- [x] Backend `backend/app/**`, `alembic/`, `tests/`
- [x] FastAPI `main.py`, config from env, **`GET /health`**, **`GET /ready`**
- [x] Alembic initialized + initial migration (all core tables + `refresh_tokens`)
- [x] Unity: HTTP client, `ApiConfig`, `*ApiService` stack, dual mock/API mode
- [x] Deploy: Ubuntu/Nginx/systemd/Postgres — **`deploy/README_DEPLOYMENT.md`** + scripts

## Phase 1 — Auth & session

- [x] Register, login, **refresh**, **`GET /auth/me`** (logout is **client-side** token clear; no `POST /auth/logout` yet)
- [x] Password hashing; refresh token **rotation** on refresh endpoint
- [x] Unity: guest + API login/register; `TokenStorageService`; `AuthApiService`

## Phase 2 — Catalogs & design CRUD

- [x] Seed `garment_templates`, `material_definitions`, `color_palettes` (dev lifespan + **`python -m app.seed`**)
- [x] API: templates, materials, palettes, designs **POST/GET/PUT/DELETE** (`GET /designs/my` for current user)
- [x] Unity: catalog-driven create flow via services (API or mocks)

## Phase 3 — Uploads & exports

- [x] `app/storage` local implementation + static mount `/static/uploads`
- [x] **`POST /uploads/image`** + **`POST/GET /exports`**
- [x] Unity: `PublishingExportService` (PNG → upload → register export) when `HasBackendSession`
- [x] Production: upload size limit, MIME allowlist, **magic-byte** validation (JPEG/PNG/WebP)

## Phase 4 — Gallery & ratings

- [x] `gallery_items` + API publish/create + public feed
- [x] Ratings 1–10 + **upsert** per user; list by gallery item
- [x] Unity: gallery, design detail, rating submit

## Phase 5 — AI placeholders

- [x] `ai_jobs` table + **`POST /ai/jobs`**, **`GET /ai/jobs/{id}`** (no separate `/ai/capabilities` yet)
- [x] Unity: `AIJobApiService` → same routes

## Phase 5b — V2 sketch pipeline & social (Prompt 6) — **in progress / first slice landed**

- [x] Backend: **`POST /ai/sketch/clean`**, **`/ai/sketch/polish`**, **`/ai/style/suggest`** (enqueue same `ai_jobs` table; placeholder completion)
- [x] Backend: gallery **`sort`**, **`gallery_likes`**, **`gallery_comments`**, optional auth on item detail → **`liked_by_me`**
- [x] Unity: sketch screens (`SketchCanvas`, `ImportSketch`, `SketchEnhancement`, `ConceptResult`), `SketchPipelineApiService` + mocks, `ScreenId` + home entry
- [x] Unity: extended **`GarmentCategory`**, design_data V2 fields (silhouette/drape/layering/seam + sketch ref), material **`metadata.v2`** mapping, preview framing presets
- [x] **Sketch capture (first slice):** in-app raster pad — `UiSketchPad` + `SketchCanvasScreen`
- [ ] Image import / picker polish; queued workers; trending beyond likes+rates; share-card export; full UX polish pass

## Phase 6 — Revisions & handoff readiness

- [x] `design_revisions` model + table (API routes **not** fully exposed as dedicated CRUD — **future**)
- [ ] Optional auto-save snapshots from editor
- [ ] Designer handoff: manifest JSON + export type (future `export_kind`)

## Phase 7 — Hardening

- [x] **Deploy runbook** + backup/restore scripts; production `.env` template; `LOG_LEVEL`; production settings validation
- [ ] Rate limits; audit logs for admin actions
- [x] Moderation fields on gallery/designs ( **`moderation_status`** ); public APIs filter **`ok`**
- [x] Backups documented (`deploy/backup_postgres.sh`); staging/prod parity **process** in README_DEPLOYMENT

---

## Future upgrade points (reference)

| Area | Upgrade |
|------|---------|
| Storage | S3-compatible; presigned uploads; CDN for thumbnails |
| AI | Queue workers; webhooks; multiple providers |
| Realtime | WebSocket/SSE for job completion |
| Auth | OAuth; device-bound tokens; optional `POST /auth/logout` |
| Scale | Read replicas, PgBouncer, horizontal API nodes |
| Compliance | COPPA/GDPR flows; content moderation pipelines |
| Monetization | Entitlements table; feature flags per tier |

_Update phase status and add/remove tasks as scope changes._
