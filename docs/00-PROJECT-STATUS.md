# FashionRise — project status & session handoff

**Purpose:** Single page to align **new chat sessions** and humans on **what exists**, **where it lives**, and **what to do next**.  
**Maintenance:** After each meaningful milestone, update the **last updated** line, **milestone table**, and **suggested next steps**. Touch **`docs/06-implementation-phases.md`** when phase checkboxes move.

**Last updated:** 2026-05-10 (platform targets: Windows + Android)

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
| **A — Sketch & authoring** | **In progress:** raster pad (`UiSketchPad`: draw, undo, clear, PNG export) wired from `SketchCanvasScreen`; next: layers/import polish, autosave, real AI workers | Prompt 6 completion, Phase 5b |
| **B — Social & growth** | Publish flow from app, share cards / deep links, richer feed, optional points/leaderboards **without** turning into a shallow game | Phase 4–5b + new product spec |
| **C — Maker handoff** | Export bundles: tech flats, spec sheets, BOM-style material summary, measurements — backend + Unity | Prompt 7 / Phase 6 |
| **D — Trust & scale** | Hardening, moderation tools, analytics, CI, optional compliance | Phase 7 + Prompt 8 |

Work **pillar by pillar**; each pillar ships incremental value to real users (including your daughter’s use case: learn, share, sew).

---

## Current state (executive)

| Area | Status | Location |
|------|--------|----------|
| **Backend API** | Implemented (FastAPI, JWT + refresh, CRUD, uploads, AI job stubs) | `backend/app/` |
| **Database** | PostgreSQL + Alembic initial migration | `backend/alembic/versions/` |
| **Unity client** | Mocks + **API mode** (switchable); screens use `AppServices` only | `FashionRise/Assets/FashionRise/` |
| **Deployment** | Ubuntu + systemd + Nginx + Postgres scripts & guide | `deploy/` |
| **Docs** | Architecture, API, DB, Unity, phases — this folder | `docs/` |

---

## Milestone tracker (prompts / major deliveries)

| Milestone | Status | Notes |
|-----------|--------|--------|
| Backend foundation (models, routes, auth, seed, Alembic) | **Done** | See `docs/03-backend.md`, `05-api.md` |
| Unity ↔ FastAPI (dual mode, *ApiService* stack) | **Done** | `docs/unity-backend-integration.md`, `unity-services.md` |
| Production deploy (Ubuntu, Nginx, Postgres, systemd) | **Done** | `deploy/README_DEPLOYMENT.md` |
| V2 Prompt 6 (sketch AI routes, gallery likes/comments/sort, extended categories) | **First slice done** | Run **`alembic upgrade head`** for `002_gallery_social_v2`; add new **Screen** objects under `ScreenController` in Unity |
| Hardening (rate limits, `/auth/logout`, admin, WebGL polish) | **Not started** | Listed under next steps |

### Original prompt series (from `docs/all prompts.txt`)

| # | Intent | Reality check |
|---|--------|----------------|
| **0** | Master context / quality bar | Ongoing guidance, not a build step. |
| **1** | Full architecture | **Done** (living docs in `docs/`). |
| **2** | Unity client V1 | **Done** (screens, mocks, services). |
| **3** | FastAPI backend V1 | **Done**. |
| **4** | Connect Unity ↔ backend | **Done** (API mode, auth, screens). |
| **5** | Production deploy | **Done** (`deploy/`). |
| **6** | V2: sketch AI, social, richer catalog, UX polish | **Partially done** — tech slice landed; **friendly “for creators” UX**, real sketch canvas, share cards, and remaining bullets are **not** finished. Extra fixes (guest sketch, login errors) were **stability polish**, not a new prompt. |
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
| Unity API mode | `FashionRiseApp` → Api Config | Same + HTTPS base URL |
| One-click API preset (Editor) | **FashionRise → Use Local API (127.0.0.1:8000) — apply to scene** | N/A |

---

## Suggested next steps (aligned with full product)

1. **Pillar A:** Extend sketch authoring — **layers or vectors**, reference import polish, **autosave / revisions API**, Guided vs Pro chrome; keep **pro** data model (design_data, exports) as source of truth. Canvas slice: `FashionRise/Assets/FashionRise/Presentation/Sketch/UiSketchPad.cs` + `SketchCanvasScreen.cs`.  
2. **Pillar B:** End-to-end **publish + share** from Create flow; social “score” can start as **ratings + likes + feed sort** before any gamified points.  
3. **Pillar C:** First **maker handoff** slice — one export package type (e.g. PDF/JSON spec + assets list) + `POST /handoff/...` minimal API.  
4. **Engineering:** Integration tests + CI; secure token storage; refresh-on-401; rate limits for production.  
5. **Prompt 8:** Formal **quality review** before marketing a “1.0” to designers and schools.

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
| 2026-05-10 | Added handoff doc; aligned with backend, Unity API mode, and `deploy/` layout. |
| 2026-05-10 | Docs sweep: `README.md` handoff workflow; `03`/`05`/`04`/`02`/Unity notes aligned with repo; deploy linked from doc index. |
| 2026-05-10 | Prompt 6 V2: backend gallery social + AI sketch routes; Unity sketch stack + UI; migration `002`. |
| 2026-05-10 | Added **Original prompt series** table — maps `all prompts.txt` to done/partial/next. |
| 2026-05-10 | **Product vision** + **roadmap pillars** (pro + beginner, social, sewing/maker handoff). |
| 2026-05-10 | **Pillar A (first slice):** `UiSketchPad` + `SketchCanvasScreen` — real raster draw, undo/clear, PNG to `persistentDataPath`, `SketchReference` as `file:…` for enhancement flow. |
| 2026-05-10 | **Platforms:** Player Settings → Android `com.fashionrise.app`, min SDK 24, target 34, ARMv7+ARM64, Internet; PC `com.fashionrise.pc`. Android gallery import (`GalleryPick.java` + manifest queries); PC “Open Imports folder”. |
