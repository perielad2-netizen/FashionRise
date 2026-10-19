# FashionRise — project status & session handoff

**Purpose:** Single page to align **new chat sessions** and humans on **what exists**, **where it lives**, and **what to do next**.
**Maintenance:** After each meaningful milestone, update the **last updated** line, **milestone table**, and **suggested next steps**.

**Last updated:** 2026-10-19 — **WEB-1** draft PR #9. Final visual/asset integration: central `uiAssets` registry, cleaned glyph/model PNGs, male croquis display asset (baked light bg removed), header branding without double FR monogram, truthful “Unsaved session” status. Pointer lifecycle from `c0322127` preserved. Domain **fashionrise.app** purchased (Cloudflare) — **no DNS/deploy in this PR**. Future hosting = isolated VPS + HTTPS same-origin app/API. WEB-1 remains **DRAFT / NOT MERGED**. Backend/Unity/AI **UNCHANGED**. Next = PM/operator visual review.

**Phase:** FashionRise Web Reboot **WEB-1** — Login → Creator Studio (tablet-first PWA)

**Baseline:** `main` / `origin/main` **`2fc4c1faa57e1e862ba9698cce6b8a7dd59bfb51`**

**WEB-1 branch:** `cursor/web-ui-reboot`

---

## Product decision (2026-10-18)

| Decision | Detail |
|----------|--------|
| Active frontend | **React / TypeScript PWA** under `web-ui/` |
| Backend | **FastAPI + PostgreSQL** preserved (JWT, uploads, designs, gallery, AI sketch pipeline, Magic, Design Book/PDF) |
| Unity | **LEGACY** — retained in `FashionRise/` for reference; **do not continue Unity UI work** for product delivery |
| Unity PR #8 | **Superseded** for active client development; **do not merge** as the product path; PM may close later |
| Reason for pivot | Unity Creator Studio visual fidelity was rejected; web enables faster iteration, true PWA/installable app feel, and a structured stroke model for future tools |
| WEB-1 Magic | Visual CTA only — **no OpenAI / paid AI calls** |
| Next after WEB-1 | Operator visual review → **WEB-2** (connect Magic to existing backend pipeline) |

---

## Development integration

| Item | Status |
|------|--------|
| PR #1 Magic Look | **MERGED** — `433b1b99` |
| PR #6 GPT-6 Luna | **MERGED** — `a5b3c167` |
| PR #7 status docs | **MERGED** — `2fc4c1fa` |
| Current `main` | **`2fc4c1fa`** |
| Unity Visual Reboot VR1 (draft PR #8) | **SUPERSEDED for active client** — not the product path; left open until PM closes |
| **WEB-1 web/PWA** | **DRAFT PR** on `cursor/web-ui-reboot` — **NOT MERGED** |
| Production deploy | **NOT PERFORMED** |
| Paid OpenAI for WEB-1 | **NONE** |
| Persistent AI/backend behavior | **UNCHANGED** |

---

## Session pause — where we stopped

**Active work:** WEB-1 tablet-first Creator Studio in `web-ui/`.

**Shipped in WEB-1:**

- Vite + React + TypeScript + React Router + Konva/perfect-freehand + PWA
- Routes: `/login` → `/studio` (session restore skips login when valid)
- Real FastAPI auth (`/auth/login`, `/auth/me`, refresh)
- Studio: Female/Male/Custom/Blank references, Draw/Erase/Undo/Redo/Clear, brush sizes, ink swatches, Dim reference
- Structured stroke history (clear undoable)
- Export utility foundation (PNG blob; not customer-facing yet)
- Magic button shows “coming in the next milestone” (no AI call)
- Docs reset: Unity marked legacy; web is active client

**Pre-operator hardening (PM review of PR #9):**

- Real `validateLogin` + LoginPage field errors; invalid submit does **not** call API/`login()`
- `exportCompositePng` uses base (bg+reference) + ink layer; eraser is ink-only
- DrawingCanvas uses **Pointer Events only** (no mouse/touch duplicate paths)
- Custom reference validates MIME (`image/jpeg|png|webp`) before object URL
- No backend / Unity / AI / paid-call changes

**Operator Windows review + drawing/asset amendment:**

- Login and Studio load succeeded in the real browser
- Visual direction approved as significantly better than the Unity Studio
- Critical bug: a click could leave drawing armed so later mouse moves continued the stroke
- Fix: pointer lifecycle requires the primary button (or an active pointer) and ends on pointerup, pointercancel, window release, and mouse `buttons` without bit 1
- Pencil sizes/freehand retuned for a finer sketch line; pen pressure is stored when the device reports it
- Selector cards use FashionRise model artwork; canvas uses female croquis + cleaned male display croquis (original male source preserved)

**Final visual & asset integration (this amendment):**

- Central registry `web-ui/src/assets/uiAssets.ts` + manifest `web-ui/docs/ASSET_MANIFEST.md`
- Icon PNGs audited (true alpha) and re-cropped to glyph-only 128×128; CSS owns button chrome
- Model-card art tightened so previews fill cream cards; selection is CSS border/glow only
- Male canvas croquis: source `/models/male_model.png` had baked near-white opaque background (looked checkerboard-like in screenshots). Runtime uses cleaned `/models/male_model_display.png`; original preserved
- Header: FashionRise logo via registry; removed redundant FR text monogram; status = **Unsaved session** (sketches are memory-only — draft persistence is a private-beta readiness requirement, not in this PR)
- Pointer regression: `pointerSession.ts` unchanged; DrawingCanvas lifecycle preserved
- Domain: **fashionrise.app** purchased through Cloudflare. Deploy plan = isolated VPS + HTTPS same-origin. **No Cloudflare DNS changes, no deploy, no production enablement in this PR**

**Do not:**

- Continue Unity UI / merge PR #8 as product
- Start WEB-2 until operator approves WEB-1 visuals
- Call OpenAI / Magic / paid AI from WEB-1
- Delete the Unity tree in this milestone
- Claim autosave / draft persistence until implemented

---

## Suggested next steps

1. **PM/operator visual review of WEB-1** at 1024×768 / 1440×900 / 768×1024 / 390×844 — assets, male croquis on cream, pointer lifecycle. Then WEB-2 only after approval.
2. Private-beta readiness: reliable sketch draft save/restore (not started).
3. After approval: **WEB-2** — connect Magic to existing backend sketch pipeline (still no Unity work). Plan fashionrise.app same-origin deploy separately (do not enable in WEB-1).
4. Broader shell nav (Home / Design Book / Discover) only after the creation workflow is excellent.
5. Optional later: Tauri packaging of the same web app for native Windows — **not** in WEB-1.

---

## Repository map

```text
FashionRise/
├── backend/                 # ACTIVE — FastAPI + PostgreSQL
├── web-ui/                  # ACTIVE — React/TS PWA Creator Studio
├── FashionRise/             # LEGACY — Unity client (reference only)
├── deploy/
├── docs/
└── README.md
```

---

## Configuration quick reference

| Concern | Dev |
|--------|-----|
| Backend env | `backend/.env` from `.env.example` |
| Web API base | `web-ui/.env` → `VITE_API_BASE_URL=http://127.0.0.1:8001/api/v1` |
| Web scripts | `cd web-ui && npm install && npm run dev` |
| Tests / build | `npm test`, `npm run build`, `npm run lint` |

---

## When you open Cursor next

1. Read **this file**.
2. Assume **`web-ui/`** is the active client unless the operator says otherwise.
3. Do **not** resume Unity Creator Studio UI work.
4. Backend: venv + `alembic upgrade head` + uvicorn on the port matching `VITE_API_BASE_URL`.
5. Frontend: `cd web-ui && npm run dev`.
6. Pick work from **Suggested next steps** (operator review → WEB-2).

---

## WEB-1 verification (this branch)

| Gate | Result |
|------|--------|
| `npm test` | Pass (Vitest) |
| `npm run build` | Pass |
| `npm run lint` | Pass (oxlint warnings only) |
| `git diff --check` | Clean expected |
| OpenAI / paid AI | **None** |
| Unity tree modified | **No** (untouched on this branch) |
| Backend/AI changed | **No** |

---

## Changelog (handoff doc only)

| Date | Summary |
|------|---------|
| 2026-10-19 | **WEB-1 final visual/asset integration (PR #9):** `uiAssets` registry + manifest; glyph/model cleanup; male croquis display asset; Unsaved session label; fashionrise.app noted (no deploy). Pointer preserved. Still draft. Next = PM/operator visual review. |
| 2026-10-18 | **WEB-1 drawing + asset pass (PR #9):** operator confirmed login/Studio and preferred the web look over Unity; pointer-up bug fixed; pencil retuned; FashionRise card/tool glyphs added. Still draft. Next = operator drawing retest. |
| 2026-10-18 | **WEB-1 pre-operator hardening (PR #9):** real login validation; export eraser ink-only; Pointer Events-only canvas; custom MIME validation. Draft/not merged. No backend/Unity/AI/paid calls. Next = operator Windows browser/PWA review. |
| 2026-10-18 | **WEB-1 web/PWA pivot:** Active client = `web-ui/` (Login → Studio). Unity marked LEGACY; PR #8 superseded for product path. Backend preserved. No paid AI. |
| 2026-10-18 | Prior Unity VR1 visual/asset notes remain historical under draft PR #8; not the active delivery path. |
| 2026-10-17 | Unity VR1 TMP / LayoutGroup / visual-fidelity amendments (historical). |
| 2026-05-12 … | Earlier Unity/backend milestones — see git history / prior rows in superseded handoffs. |
