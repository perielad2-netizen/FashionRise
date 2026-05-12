# FashionRise — Implementation phases

**Living checklist.** Update checkboxes and notes when work completes. For a **one-page handoff**, see [`00-PROJECT-STATUS.md`](./00-PROJECT-STATUS.md).

---

## Product pillars — full FashionRise (pro + beginners + makers)

_Check these off as slices ship. Same codebase: **Pro** depth, **Guided** mode for approachable UX._

### Pillar A — Serious sketch & authoring

- [x] Raster sketch surface: draw, undo stack, clear, PNG export — `Presentation/Sketch/UiSketchPad.cs`, wired from `SketchCanvasScreen` (`SketchReference` → `file:…` under persistent data)
- [x] Local image import: `persistentDataPath/Sketches` + **`Imports`** (PNG/JPEG), Import screen — **Pipeline** (as-is) vs **Trace** (underlay on `UiSketchPad`); **Android** gallery + **PC** Imports folder + **iOS** Photos picker
- [x] Dual raster layers (reference + ink): default **female/male** underlay from **`Resources/SketchReference/female_model`** / **`male_model`** (PNG), procedural fallback if missing; **Custom** via Import → Trace; **Blank paper**; **Dim/Bright ref**; pro ink row. Export flattened PNG.
- [ ] Vector / per-stroke model; export beyond local PNG (**Android** gallery + **iOS** Photos + PC folder opener **done**)
- [x] Revision snapshot **API** (`POST` / `GET` `/designs/{id}/revisions`, `GET` `/designs/{id}/revisions/{n}`) — owner only; **Unity** timed autosave + save draft + revision append
- [x] AI jobs: **in-process worker** + optional **`python -m app.ai_worker`**; sketch pipeline uses **OpenAI vision** when configured (`OPENAI_API_KEY`, etc.), else **stub** completion — see `backend/scripts/check_sketch_ai.py`
- [x] Guided vs Pro UI toggle — **`AuthoringModePreferences`** (PlayerPrefs) + **Settings** “Toggle Guided / Pro mode”; **Home** shows current mode; **Create design** hides pro-only controls (V2 garment toggles, model preview, revision history block, handoff/PDF tools, PC Handoffs folder) in **Guided** mode

### Pillar B — Share & social proof

- [x] Publish to gallery from **Create design** (preview upload uses `ExportRequest.SkipExportRegistration` — no extra `POST /exports`; then `POST /gallery` with `image_url`; opens Gallery)
- [x] Share link + **share card** (plain text: title, URL, optional preview `image_url` line) — `IShareLinkService`, HTTPS base or `fashionrise://gallery/{id}`; clipboard on publish + Design detail buttons
- [x] Feed discovery — backend `GET /gallery?sort=` (`newest` | `top_rated` | `trending` | **`following`** auth); Unity **Gallery**: **Newest / Top rated / Trending / Following** + **Refresh feed** (`GalleryScreen.cs`)
- [x] **Follow creators** — `user_follows` table + `POST/DELETE /profiles/{user_id}/follow`, `GET …/follow-status`, `GET /profiles/me/following-ids`; gallery `sort=following`; Unity `IFollowService`, **Design detail** Follow/Unfollow (`alembic` revision **003**)
- [x] **Per-creator discovery** — `GET /gallery/user/{user_id}`; Unity `IGalleryService.GetUserPublicGalleryAsync`, `GalleryNavContext`, **Creator gallery** mode + **Community feed (all creators)** escape, **Design detail** “Open creator's public gallery”, **Profile** “My public gallery”
- [x] **Comments UX** — Design detail multiline comment field + **Post comment** (server max 4000 chars)
- [x] Fair reputation model **v1** — transparent **computed** `reputation_score` (0–100 cap) + **`reputation_tier`** (`newcomer` / `rising` / `established` / `icon`) on **`GET /profiles/me`** and **`GET /profiles/{id}`**; aggregates (`published_count`, `likes_received_count`, `rating_count`, followers); Unity **Profile** displays score + tier + followers. **Next:** optional breakdown payload, anti-gaming review, tuning

### Pillar C — Real garment / sewing path

- [ ] Maker handoff **packages** (zip / multi-file atelier drops) — beyond JSON + single placeholder PDF
- [x] Backend **handoff** read: **`GET /designs/{id}/handoff`** + query **`export_kind`** (`manifest_v1` | `spec_sheet_v1` | `spec_sheet_pdf`); placeholder PDF writes storage + **`DesignExport`**; Unity **`IDesignHandoffService`** + Create/Detail UX (copy, generate, open/share/download, save JSON)
- [ ] Optional: print-friendly / PDF pipeline for atelier or classroom

### Pillar D — Trust & launch readiness

- [ ] Prompt 8 quality review; security pass; moderation admin path; CI and staging

---

## Phase 0 — Foundation

- [x] Repo layout: Unity `FashionRise/Assets/FashionRise/**` (screens, mocks, API adapters)
- [x] Backend `backend/app/**`, `alembic/`, `tests/`
- [x] FastAPI `main.py`, config from env, **`GET /health`**, **`GET /ready`**
- [x] Alembic initialized + migrations **`001`–`003`** (core tables + gallery social + `user_follows`); **downgrades** use **`if_exists`** on index/table drops for recovery when `alembic_version` is ahead of real schema
- [x] Unity: HTTP client, `ApiConfig`, `*ApiService` stack, dual mock/API mode (**default: API** for dev)
- [x] Deploy: Ubuntu/Nginx/systemd/Postgres — **`deploy/README_DEPLOYMENT.md`** + scripts

## Phase 1 — Auth & session

- [x] Register, login, **refresh**, **`GET /auth/me`**; Unity **Sign out** (client token clear + `CreateDesignSession.Reset` + `ResetToAsync` login screen). Server `POST /auth/logout` optional later
- [x] Password hashing; refresh token **rotation** on refresh endpoint
- [x] Unity: API login/register (no guest); persisted-session restore on splash; `TokenStorageService`; `AuthApiService`

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

- [x] `gallery_items` + API publish/create + public feed + **`GET /gallery/user/{user_id}`** (public posts by owner)
- [x] Ratings 1–10 + **upsert** per user; list by gallery item
- [x] Unity: gallery (global sorts + **filtered creator view**), design detail (rating **1–10**, comments, follow, creator gallery link), profile (**following count**, **My public gallery**)

## Phase 5 — AI placeholders

- [x] `ai_jobs` table + **`POST /ai/jobs`**, **`GET /ai/jobs/{id}`** (no separate `/ai/capabilities` yet)
- [x] Unity: `AIJobApiService` → same routes

## Phase 5b — V2 sketch pipeline & social (Prompt 6) — **in progress / first slice landed**

- [x] Backend: **`POST /ai/sketch/clean`**, **`/ai/sketch/polish`**, **`/ai/style/suggest`** (enqueue `ai_jobs`; **OpenAI**-backed worker when configured, else stub)
- [x] Backend: gallery **`sort`**, **`gallery_likes`**, **`gallery_comments`**, optional auth on item detail → **`liked_by_me`**
- [x] Unity: sketch screens (`SketchCanvas`, `ImportSketch`, `SketchEnhancement`, `ConceptResult`), `SketchPipelineApiService` + mocks, `ScreenId` + home entry
- [x] Unity: extended **`GarmentCategory`**, design_data V2 fields (silhouette/drape/layering/seam + sketch ref), material **`metadata.v2`** mapping, preview framing presets
- [x] **Sketch capture (first slice):** in-app raster pad — `UiSketchPad` + `SketchCanvasScreen`
- [x] **Publish gallery preview (Editor/PC):** `ScreenCapture.CaptureScreenshot` uses **full path** under `persistentDataPath` so preview upload finds the PNG (`UnityPngExportService`)
- [ ] Image import / picker polish; share-card export; full UX polish pass

## Phase 6 — Revisions & handoff readiness

- [x] `design_revisions` model + table + **CRUD-style** list/create/read on `/designs/{id}/revisions`
- [x] Unity: `SaveDraftAsync` (API) updates row then **best-effort** `POST …/revisions`; `PersistedDesignId` fixes repeat saves; revision UI includes **Show revision history**, revision selection (**newer/older**), **Restore selected revision values**, and **Restore latest revision values** (applies revision `design_data` snapshot back onto current Create session)
- [x] Timed autosave: `DesignAutosaveDriver` + Settings (interval 15–900s, default 60; on/off); signed-in + API tokens when using backend
- [x] Designer handoff **read path shipped:** `GET /designs/{id}/handoff` + **`export_kind`** (`manifest_v1`, `spec_sheet_v1`, `spec_sheet_pdf` placeholder + registered export); revision summary + export hints in manifest. **Remaining:** real PDF/spec packages, zip handoff, measurements/BOM depth

## Phase 7 — Hardening

- [x] **Deploy runbook** + backup/restore scripts; production `.env` template; `LOG_LEVEL`; production settings validation
- [x] **HTTP rate limits** (SlowAPI per IP / `X-Forwarded-For` — auth, uploads, AI routes); see `backend/README.md` Security notes
- [ ] Audit logs for admin actions
- [ ] CI (GitHub Actions or similar) running **`pytest`** on backend PRs
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
