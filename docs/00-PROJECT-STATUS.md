# FashionRise — project status & session handoff

**Purpose:** Single page to align **new chat sessions** and humans on **what exists**, **where it lives**, and **what to do next**.  
**Maintenance:** After each meaningful milestone, update the **last updated** line, **milestone table**, and **suggested next steps**. Touch **`docs/06-implementation-phases.md`** when phase checkboxes move.

**Last updated:** 2026-10-17 (Visual Reboot **VR1** — Creator Studio shell on `cursor/visual-reboot-studio-shell`. Baseline `origin/main` **`2fc4c1fa`**. Production deploy **NOT PERFORMED**. Paid OpenAI for VR1 **NONE**. Persistent AI/backend **UNCHANGED**.)

**Phase:** FashionRise Visual Reboot VR1 — Creator Studio Shell + Premium Design System

**Baseline:** `main` / `origin/main` **`2fc4c1fa`** (PR #7 docs merge; contains Magic Look PR #1 `433b1b99` + GPT-6 Luna PR #6 `a5b3c167`).

**VR1 implementation commit:** `9bfa88bb1733149ad0cadf3a991544a11f3b8d14` (`9bfa88bb`).

**Development integration (corrected 2026-10-17):**

| Item | Status |
|------|--------|
| PR #1 Magic Look | **MERGED** — `433b1b99` (poll fail-fast `614424c2`) |
| PR #6 GPT-6 Luna | **MERGED** — `a5b3c167` (rebased onto #1; default `gpt-6-luna`) |
| PR #7 status docs | **MERGED** — `2fc4c1fa` |
| Current `main` / `origin/main` | **`2fc4c1fa`** (not `a5b3c167`) |
| Visual Reboot VR1 | **DRAFT PR** — Studio shell + design system only; not merged |
| Production deploy | **NOT PERFORMED** |
| Paid OpenAI for VR1 | **NONE** |
| Persistent AI/backend behavior | **UNCHANGED** |

**Unity evidence (operator, 2026-10-17, Unity `2022.3.62f1`) — corrects stale “Unity compile NOT RUN”:**

| Gate | Status |
|------|--------|
| Windows batch compile/load | **PASS**, process exit **0** |
| EditMode XML | **0 tests**, 0 failures, 0 errors |
| PlayMode XML | **0 tests**, 0 failures, 0 errors |
| Meaning | Compilation/load evidence — **not** automated behavioral coverage |
| Manual Play Mode baseline (2026-10-17) | **PASS** |

These XML files must **not** be reported as “Unity tests passed.” Correct phrasing: Unity batch Editor load/compile completed successfully; automated test coverage remains 0.

**Manually verified on that baseline (do not re-spend OpenAI for VR1):** local auth, model selection, sketching, Magic, GPT-6 Luna Chat Completions, gpt-image-1 edit, Magic result display, Create Real Design, front/back/pattern assets, tech-pack PDF.

**Magic Look PR #1 (merged 2026-10-17):** poll fail-fast (`AiJobPollPolicy`) is on `main` (`614424c2`). Isolated Postgres API tests previously **7 passed**.

**GPT-6 Luna close-out (2026-10-16, operator live report + PM review):**

| Gate | Status |
|------|--------|
| Chat Completions live compatibility | **VALIDATED — 3/3** synthetic scenarios (`sketch_clean`, `sketch_polish`, `style_suggest`) |
| Production deployment | **NOT PERFORMED** |
| Magic Look dependency | **PR #1 MERGED** (`433b1b99`) |
| PostgreSQL integration tests | **VALIDATED** earlier on isolated disposable Postgres (not an app DB) |
| Unity 2022.3.62f1 Windows batch compile/load | **PASS**, exit 0 (operator). Automated tests remain **0**. |
| Manual Play Mode baseline 2026-10-17 | **PASS** |
| Next | Do **not** repeat the paid live harness. Do **not** deploy from VR1. After operator visual review, **VR2 — Professional Sketch Tools**. |

**Source repo:** [github.com/perielad2-netizen/FashionRise](https://github.com/perielad2-netizen/FashionRise) (default branch **`main`**). Root **`.gitignore`** excludes `backend/.env`, Unity `Library/` / `Logs/` / `UserSettings/`, etc.

---

## Session pause — where we stopped (read this first in a new chat)

**As of this pause:** local **Postgres** is the source of truth for auth; dev recovery remains **`alembic downgrade base`** → **`alembic upgrade head`** ( **`if_exists`-safe** downgrades on `001`–`003`** ) when `alembic_version` and real tables disagree (**wipes app data** in that DB). **Uvicorn** clean when migrations match.

**Recently shipped (high level):**

- **Backend:** Same as prior milestone (reputation v1 on profiles, handoff `export_kind`, rate limits, `.env` absolute path, pytest flows). **Auth tweaks:** `auth_service` stores **lowercased** email, login matches **case-insensitively**; **password strip** on register/login to avoid stray whitespace; dev helper **`python scripts/set_user_password.py email "password"`** (see `backend/README.md` → Dev utilities). **`401` login** vs **`409` register** = invalid credentials vs duplicate email/username (not the same root cause).
- **Unity — sketch (Pillar A):** **Dual-layer** `UiSketchPad` unchanged (reference + ink, composite PNG export). **Default models:** `Resources/SketchReference/female_model.png` & `male_model.png`. **VR1 Creator Studio:** `SketchCanvasScreen` is now a navy/cream shell (`FrStudioShell` + top bar, model cards, tool rail, inspector, Magic CTA) composed from `FashionRise/UI/Studio/*`. Existing Female/Male/Custom/Blank, Dim ref, brush sizes, colors, Draw/Erase, Undo, Clear, and **Magic → save PNG + `NavigateTo(SketchEnhancement)`** are preserved. Pad bootstrap remains in **`OnShown`**. Home and other screens stay on legacy `FrUiFactory` + `UnityEngine.UI.Text`.
- **VR1 known limitations:** Cloud agent has **no Unity Editor**, so VR1 Play Mode was **not** human-validated here. No TMP font assets are committed; typography uses TMP when `TMP_Settings.defaultFontAsset` or a Resources font exists, otherwise **UI.Text fallback**. `UiSketchPad` still has **no flood-fill engine** (pre-VR1 color = brush swatches only). Narrow/portrait reflows side rails into a top model strip + bottom dock — operator should resize Game view. Programmatic icons, not a purchased icon set. Canvas uses `AspectRatioFitter` 768:1024 to protect draw coordinates.
- **Unity — platform:** **iOS Photos** → `Imports` (`FashionRiseGalleryPickBridge.mm`, `IOSGalleryPick`, shared `FashionRiseAndroidBridge` UnitySendMessage). **Guided/Pro**, share sheet, gallery/social, design detail nullable `RawImage.texture` clear (`null!`).
- **Tooling / meta:** Fixed **invalid 32-char Unity GUIDs** on new `.meta` files (was breaking `SketchFigureTemplate` compile). **`FashionRise.asmdef`** duplicate `precompiledReferences` key removed.

**Suggested order for the *next* session:**

1. **Operator visual review of VR1** on Unity **2022.3.62f1** (App scene → Play → login → Creator Studio). Use the VR1 manual checklist. Do **not** run Magic solely for this visual PR. Do **not** merge or deploy until that review.
2. After approval: **Visual Reboot VR2 — Professional Sketch Tools** (Pencil/Marker/Brush/Fill/Gradient, layers foundation). Do **not** start VR2 from this draft.
3. **Pillar C:** Real **`spec_sheet_pdf`** layout (or second export kind); zip / multi-file handoff when ready.
4. **Pillar B:** Reputation **v2** explainability; gallery/sketch **UX polish** on remaining legacy screens.
5. **Pillar D:** **CI** + `pytest`; Prompt 8 when targeting a release candidate.

**Parking lot (unchanged intent):** full AI worker split at scale, WebGL polish, `POST /auth/logout`, admin moderation UI, audit logs.

---

## Product vision (north star)

FashionRise is a **professional fashion sketch and design app** — credible for **working designers**, and **approachable** for **beginners** (including younger creators) who want a serious starting point, not a toy dress-up app.

- **Sketch & design:** Real sketch workflows, garment logic, materials, and exports that hold up in a portfolio or classroom.
- **Social proof:** Share designs, compare looks, **ratings** and (over time) **reputation / discovery** so the community can see which work resonates — fun and motivating, still respectful.
- **Real life & sewing:** A clear path from digital design to **physical garment**: specs, handoff packages, measurements placeholders, and collaboration hooks so ideas can move toward **cutting fabric and machine sewing** (e.g. student / maker / small atelier use cases).

**Principle:** One **technical architecture** (services, API, moderation-ready backend). Two **experience layers**: optional **Guided / Studio** mode for newcomers and **Pro** density for experts — same app, different chrome and defaults.

---

## Roadmap pillars (execution order)

| Pillar | Outcome | Ties to |
|--------|---------|--------|
| **A — Sketch & authoring** | **In progress:** dual-layer pad + default **PNG croquis** + Import + **VR1 Creator Studio shell** (draft); **next after VR1 approval:** VR2 professional tools, then vector/layers/export beyond flat PNG | Prompt 6 completion, Phase 5b, Visual Reboot |
| **B — Social & growth** | **In progress:** feeds, follows, per-creator gallery, ratings 1–10, comments, share/native share; **reputation v1** (computed score + tier on profile API + Unity Profile). Next: UX polish, notifications, reputation explainability | Phase 4–5b |
| **C — Maker handoff** | **First slice shipped:** `GET …/handoff` + `export_kind` (`manifest_v1`, `spec_sheet_v1`, `spec_sheet_pdf` placeholder + file URL + export row). Next: real PDF/spec packages, richer BOM/measurements | Prompt 7 / Phase 6 |
| **D — Trust & scale** | Hardening, moderation tools, analytics, CI, optional compliance | Phase 7 + Prompt 8 |

Work **pillar by pillar**; each pillar ships incremental value to real users (including your daughter’s use case: learn, share, sew).

---

## Current state (executive)

| Area | Status | Location |
|------|--------|----------|
| **Backend API** | Implemented (FastAPI, JWT + refresh, CRUD, uploads, gallery social + follows, AI jobs — **OpenAI vision** for sketch pipeline when keys + worker configured, else stub) | `backend/app/` |
| **Database** | PostgreSQL + Alembic **`001`–`003`**; downgrades use **`if_exists`** for recovery on stamped-but-empty DBs | `backend/alembic/versions/` |
| **Unity client** | **API mode default**; gallery + creator filter; design detail (rate, follow, comment, **native share**, handoff **copy / spec JSON / PDF gen+open+share+download / save file**, PC Handoffs folder); profile (**reputation v1**, Refresh, following, my gallery); create (**Guided/Pro**, revisions UI, publish); **iOS** sketch import via Photos → `Imports` (`IOSGalleryPick` + native bridge); use **`UnityEngine.Application`** where needed | `FashionRise/Assets/FashionRise/` |
| **Deployment** | Ubuntu + systemd + Nginx + Postgres scripts & guide | `deploy/` |
| **Docs** | Architecture, API, DB, Unity, phases — this folder | `docs/` |

---

## Milestone tracker (prompts / major deliveries)

| Milestone | Status | Notes |
|-----------|--------|--------|
| Backend foundation (models, routes, auth, seed, Alembic) | **Done** | See `docs/03-backend.md`, `05-api.md` |
| Unity ↔ FastAPI (dual mode, *ApiService* stack) | **Done** | `docs/unity-backend-integration.md`, `unity-services.md` |
| Production deploy (Ubuntu, Nginx, Postgres, systemd) | **Done** | `deploy/README_DEPLOYMENT.md` |
| V2 Prompt 6 (sketch AI routes, gallery likes/comments/sort, extended categories) | **First slice done** | `alembic upgrade head` includes **`002`** (gallery social) + **`003`** (`user_follows`); Unity sketch + gallery stack shipped |
| Hardening (SlowAPI rate limits on auth/uploads/AI; `/auth/logout`, admin, WebGL polish) | **Partial** — **rate limits** shipped (`backend/app/core/rate_limit.py`); logout/admin/WebGL TBD |

### Original prompt series (from `docs/all prompts.txt`)

| # | Intent | Reality check |
|---|--------|----------------|
| **0** | Master context / quality bar | Ongoing guidance, not a build step. |
| **1** | Full architecture | **Done** (living docs in `docs/`). |
| **2** | Unity client V1 | **Done** (screens, mocks, services). |
| **3** | FastAPI backend V1 | **Done**. |
| **4** | Connect Unity ↔ backend | **Done** (API mode, auth, screens). |
| **5** | Production deploy | **Done** (`deploy/`). |
| **6** | V2: sketch AI, social, richer catalog, UX polish | **Partially done** — tech slice landed; **friendly “for creators” UX**, real sketch canvas, share cards, and remaining bullets are **not** finished. Extra fixes (sketch pipeline, login errors) were **stability polish**, not a new prompt. |
| **7** | V3 / pro platform (handoff packages, challenges, revisions API, …) | **Not started** — large scope; plan in slices. |
| **8** | Final architecture / quality **review** (report + checklist) | **Not started** — best after V2 closure or before a release candidate. |

**Product note:** The prompt file targets a **premium creator tool** (serious, not “dress-up”). Younger players still need **simple flows and gentle copy** — that’s mostly **UX work** on top of the same architecture, not a different product.

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
├── docs/                    # This documentation set (+ 00-PROJECT-STATUS.md)
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
| One-click API preset (Editor) | **FashionRise → Use Local API (127.0.0.1:8000) — apply to scene** | N/A |

---

## When you open Cursor next (start here)

1. Read **this file** through **Suggested next steps** (below).
2. **Pull** latest if you work from another machine: `git pull origin main`.
3. **Backend:** `cd backend`, activate venv, ensure **`backend/.env`** exists (copy from `.env.example`) — the app **always** reads this path, not cwd-relative `.env`. Postgres running, **`alembic upgrade head`**, start API (e.g. uvicorn). If tables are missing but `alembic current` shows head, run **`alembic downgrade base`** then **`alembic upgrade head`** (dev reset; wipes app data in that DB).
4. **Unity:** open project `FashionRise/`, scene **App**, Press Play — client expects **FastAPI** at `http://127.0.0.1:8000/api/v1` unless you enable mocks on `FashionRiseApp`.
5. Pick work from **Suggested next steps** or **Pillar A** unchecked items in `06-implementation-phases.md`; after a milestone, update **Last updated** + **Changelog** here.

---

## Suggested next steps (aligned with full product)

1. **Visual Reboot VR1 (this draft):** operator Play Mode visual checklist on the Studio shell. Then **VR2** professional sketch tools. Do not merge old UI PRs #2/#3/#4.
2. **Pillar A — authoring depth:** **Layers/vectors** (or structured stroke model) on `UiSketchPad` after VR2 foundations; export beyond local PNG where product needs it. (**iOS** Photos → Imports picker shipped; **Android** + **PC** unchanged.)
3. **Pillar C — handoff quality:** Evolve **`spec_sheet_pdf`** from placeholder bytes to a real layout; add measurement/BOM fields to manifest + Unity “save package” flow when ready.
4. **Pillar B — polish:** Toasts / less error-as-body-text; optional **notifications**; **reputation explainability** (small JSON breakdown on profile or docs for creators).
5. **Engineering:** **CI** running `pytest`; secure token storage on mobile; refresh-on-401 hardening.
6. **Prompt 8:** Formal **quality review** before a public “1.0” narrative.

_Update this list as pillars complete._

---

## Doc index (what to read when)

| Question | Doc |
|----------|-----|
| What is the system? | `01-architecture-overview.md` |
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
| 2026-10-17 | **Visual Reboot VR1 (draft):** Creator Studio shell + premium design system on `cursor/visual-reboot-studio-shell` (`9bfa88bb`) from `origin/main` **`2fc4c1fa`**. New `FashionRise/UI/Studio` components; `SketchCanvasScreen` rebuilt around unchanged `UiSketchPad` + existing Magic path (`ContinueToEnhancement` → `SketchEnhancement`). Theme tokens + `DeviceLayoutPolicy` wide/narrow. TMP foundation with UI.Text fallback. **No** backend/AI/contract changes. **No** VR2 tools. **No** fill/pencil/gradient/layers/fabric engines. Unity CLI **not available** in the cloud agent; operator 2022.3.62f1 Windows batch compile/load **PASS** exit 0 on baseline; EditMode/PlayMode XML **0 tests**. Paid OpenAI **NONE**. Production deploy **NOT PERFORMED**. |
| 2026-05-12 | **Unity iOS:** `IOSGalleryPick` + `FashionRiseGalleryPickBridge.mm` (PHPicker iOS 14+, UIImagePicker 12–13); `Plugins/iOS/Info.plist` `NSPhotoLibraryUsageDescription`; Import screen **Pick from Photos**; `FashionRiseApp` creates `FashionRiseAndroidBridge` on iOS for `UnitySendMessage`. Docs: **`06`**, **`00`**, **`README_Unity`**. |
| 2026-05-11 | **Session pause doc sweep:** `00` handoff block (where we stopped / next picks); pillars + executive table refreshed; startup DB notes (`backend/.env` absolute, migration recovery). Related: **`06`**, **`05-api`**, **`02-unity-client`**, **`03-backend`**, **`04-database`**, **`unity-backend-integration.md`**, **`backend/README`**, **`README_Unity`**, **`docs/README`**, root **`README`**. |
| 2026-05-11 | **Backend ops & migrations:** Alembic **`001`/`002`/`003` downgrades** use **`if_exists`** on drops (recover stamped-without-tables DBs). **`app/core/config.py`** loads **`backend/.env`** by path. Lifespan: seed + schema warning + AI worker single-warning stop on missing tables. |
| 2026-05-11 | **Reputation v1:** `ProfileRead` + `profile_service.build_profile_read` — `reputation_score`, `reputation_tier`, aggregates; Unity **Profile** + **`UserProfileApiService`** stats mapping. |
| 2026-05-11 | **Unity:** **`NativeShareSheet`** + iOS bridge; share link/card/PDF URL; PDF download; **`PcHandoffsFolderOpener`**; **`AuthoringModePreferences`** + Home/Settings/Create **Guided/Pro**; **`UnityEngine.Application`** fixes in Create/Design detail. |
| 2026-05-11 | **Pillar B (Unity + API wiring):** `IGalleryService.GetUserPublicGalleryAsync` → `GET /gallery/user/{user_id}`; `GalleryNavContext` (**`OwnerUserId`**, optional **`CommunitySort`**) + **Creator gallery** / **Community feed (all creators)** on `GalleryScreen`; **Back** to gallery preserves creator filter + sort; **Home** “Following feed (gallery)”; **Design detail** → **Open creator's public gallery**; **Profile** → **My public gallery**, **Refresh**, **Following: N**; **Post comment** with multiline field (≤4000 chars); rating **1–10**; maker handoff **Save to file** under `persistentDataPath/Handoffs`. |
| 2026-05-11 | **Publish preview (Editor/PC):** `UnityPngExportService` passes **full path** to `ScreenCapture.CaptureScreenshot` so PNG is under `persistentDataPath` and `PublishingExportService` can upload; longer wait before read on upload. |
| 2026-05-11 | **Pillar A:** `POST`/`GET` `/api/v1/designs/{id}/revisions` (+ single revision `GET`) for autosave/history snapshots (owner-only). |
| 2026-05-11 | **Unity:** API `SaveDraftAsync` appends revision after save; `CreateDesignSession.PersistedDesignId` so repeat **Save draft** updates the same design. |
| 2026-05-11 | **Unity:** timed draft autosave (`DesignAutosaveDriver`), PlayerPrefs interval + Settings toggle. |
| 2026-05-11 | **Unity:** removed guest login; API `TryRestorePersistedSessionAsync` on splash; sketch pipeline renamed `TokenAwareSketchPipelineService`. |
| 2026-05-11 | **Unity:** Settings **Sign out**; `INavigationService.ResetToAsync` clears back stack; session + `CreateDesignSession.Reset` on logout. |
| 2026-05-11 | **Pillar B slice:** Create design **Publish to gallery** + `IGalleryService.PublishDesignAsync` (API + mock). |
| 2026-05-11 | **Unity:** Gallery publish runs **Export PNG** first (API); `ExportResult.UploadedImageUrl` fills `POST /gallery` `image_url`. |
| 2026-05-11 | **Unity:** `ExportRequest.SkipExportRegistration` — gallery preview upload skips `POST /exports`. |
| 2026-05-11 | **Pillar B:** share links + clipboard share card (`IShareLinkService`, `ApiConfig` web base or custom scheme). |
| 2026-05-10 | Added handoff doc; aligned with backend, Unity API mode, and `deploy/` layout. |
| 2026-05-10 | Docs sweep: `README.md` handoff workflow; `03`/`05`/`04`/`02`/Unity notes aligned with repo; deploy linked from doc index. |
| 2026-05-10 | Prompt 6 V2: backend gallery social + AI sketch routes; Unity sketch stack + UI; migration `002`. |
| 2026-05-10 | Added **Original prompt series** table — maps `all prompts.txt` to done/partial/next. |
| 2026-05-10 | **Product vision** + **roadmap pillars** (pro + beginner, social, sewing/maker handoff). |
| 2026-05-10 | **Pillar A (first slice):** `UiSketchPad` + `SketchCanvasScreen` — real raster draw, undo/clear, PNG to `persistentDataPath`, `SketchReference` as `file:…` for enhancement flow. |
| 2026-05-10 | **Platforms:** Player Settings → Android `com.fashionrise.app`, min SDK 24, target 34, ARMv7+ARM64, Internet; PC `com.fashionrise.pc`. Android gallery import (`GalleryPick.java` + manifest queries); PC “Open Imports folder”. |
| 2026-05-10 | **Dev defaults:** Unity **`ApiConfig`** API-on / mock-off; `AppServices` no longer falls back to mocks when `BaseUrl` empty (loud error + still API stack). Root **`.gitattributes`**, **`.gitignore`**, Plugins/Android **`.meta`** for stable GUIDs. |
| 2026-05-10 | **GitHub:** initial push to **`perielad2-netizen/FashionRise`** on branch **`main`**. |
