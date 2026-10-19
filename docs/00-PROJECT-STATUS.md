# FashionRise — project status & session handoff

**Purpose:** Single page to align **new chat sessions** and humans on **what exists**, **where it lives**, and **what to do next**.
**Maintenance:** After each meaningful milestone, update the **last updated** line, **milestone table**, and **suggested next steps**.

**Last updated:** 2026-10-19 — **WEB-V2** functional Studio integration on draft PR #9. WEB-V1 design-lab visual direction was **approved**. Production `/studio` now uses the approved shell (`web-ui/src/shell/`) with the real Konva drawing engine, pointer lifecycle, models, brush/color/settings, and truthful **Unsaved session** status. Future-only controls remain disabled. Magic remains notice-only (no paid AI). `/_design/studio` kept DEV-only for visual regression. Beta blockers: reliable draft persistence + private access controls. Deploy target **fashionrise.app** (Cloudflare + isolated VPS) — **no DNS/deploy**. Next = PM review, then persistence / private-beta hardening. No merge / deploy in this milestone.

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

**Final visual & asset integration:**

- Central registry `web-ui/src/assets/uiAssets.ts` + manifest `web-ui/docs/ASSET_MANIFEST.md`
- Male canvas croquis display asset; Unsaved session label; pointer lifecycle preserved

**WEB-V1 — design-lab mockup reconstruction:**

- DEV-only `/_design/studio`; visual direction **approved** by PM/operator
- Report: `docs/WEB-V1-VISUAL-QA.md`

**WEB-V2 — functional Studio integration (this amendment):**

- Production `/studio` renders approved shell from `web-ui/src/shell/` + `useStudioEditor`
- Real Konva drawing (`DrawingCanvas` + `pointerSession`); single canvas; 768×1024 design space
- Connected: Pencil/Eraser, Undo/Redo, Clear (overflow), Female/Male/Custom/Blank, brush size/opacity, colors/hex, dim reference, Sign out, Magic notice
- Disabled/unavailable: future tools, fabrics/gradients/layers actions, canvas resize, pressure toggle, nav destinations beyond Create, Help tab, zoom chrome
- Status: **Unsaved session** (no fake Auto Save)
- Magic / Generate with AI: polished later-milestone notice only — **no OpenAI / paid calls**
- Mobile: floating brush card hidden; **Brush panel** bottom sheet
- Visual QA: `docs/WEB-V2-VISUAL-QA.md`
- Current beta blockers: reliable draft saving/restoration; private access controls
- Deploy target: **fashionrise.app** via Cloudflare + isolated VPS — **not enabled in this PR**

**Do not:**

- Continue Unity UI / merge PR #8 as product
- Start persistence / private-beta deploy / paid AI in this milestone
- Claim autosave / draft persistence until implemented
- Merge PR #9

---

## Suggested next steps

1. **PM review of WEB-V2 `/studio`** (composition + functional acceptance).
2. Reliable draft persistence + private-beta hardening.
3. Later: fashionrise.app deploy (Cloudflare DNS + isolated VPS) — not in this PR.
4. Later: Magic/backend connection after beta readiness.
5. Optional later: Tauri packaging.

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
| 2026-10-19 | **WEB-V2 functional Studio integration (PR #9):** approved shell promoted to `/studio` with real drawing/tools/models; design-lab retained DEV-only; Magic disabled; Unsaved session truthful. Still draft. Next = PM review → persistence/private-beta. |
| 2026-10-19 | **WEB-V1 design-lab reconstruction (PR #9):** DEV-only `/_design/studio` full mockup visual prototype; production `/studio` preserved. Features in lab are not production. Visual direction later approved for WEB-V2. |
| 2026-10-19 | **WEB-1 final visual/asset integration (PR #9):** `uiAssets` registry + manifest; glyph/model cleanup; male croquis display asset; Unsaved session label; fashionrise.app noted (no deploy). Pointer preserved. Still draft. Next = PM/operator visual review. |
| 2026-10-18 | **WEB-1 drawing + asset pass (PR #9):** operator confirmed login/Studio and preferred the web look over Unity; pointer-up bug fixed; pencil retuned; FashionRise card/tool glyphs added. Still draft. Next = operator drawing retest. |
| 2026-10-18 | **WEB-1 pre-operator hardening (PR #9):** real login validation; export eraser ink-only; Pointer Events-only canvas; custom MIME validation. Draft/not merged. No backend/Unity/AI/paid calls. Next = operator Windows browser/PWA review. |
| 2026-10-18 | **WEB-1 web/PWA pivot:** Active client = `web-ui/` (Login → Studio). Unity marked LEGACY; PR #8 superseded for product path. Backend preserved. No paid AI. |
| 2026-10-18 | Prior Unity VR1 visual/asset notes remain historical under draft PR #8; not the active delivery path. |
| 2026-10-17 | Unity VR1 TMP / LayoutGroup / visual-fidelity amendments (historical). |
| 2026-05-12 … | Earlier Unity/backend milestones — see git history / prior rows in superseded handoffs. |
