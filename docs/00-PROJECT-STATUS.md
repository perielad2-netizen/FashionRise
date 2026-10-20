# FashionRise — project status & session handoff

**Purpose:** Single page to align **new chat sessions** and humans on **what exists**, **where it lives**, and **what to do next**.
**Maintenance:** After each meaningful milestone, update the **last updated** line, **milestone table**, and **suggested next steps**.

**Last updated:** 2026-10-20T12:45Z. **WEB-V3A** is **merged** (PR [#13](https://github.com/perielad2-netizen/FashionRise/pull/13) → `85b6561b`) and **DEPLOYED** to production. Operator **physical-device acceptance is still pending**. Do not start WEB-V3B. Do not enable AI, uploads, Gallery, or registration.

**Phase:** **WEB-V3A** live on the protected family beta: Export PNG, Save as design, My Designs, and safe reopen.

**Production (`https://fashionrise.app`, behind Cloudflare Access + Authenticated Origin Pulls):**

| Layer | Revision |
|---|---|
| Frontend (`web-ui`) | **`85b6561b338e31c102d101c8d458a1624e7b9f29`** — Nginx root `/var/www/fashionrise/releases/85b6561b` (WEB-V3A). Previous release retained: `f8a5b22`. |
| Backend (FastAPI + PostgreSQL) | **`85b6561b338e31c102d101c8d458a1624e7b9f29`** — unit `fashionrise-api`, `127.0.0.1:8010`. Previous: `6df327ba`. |
| Database | `fashionrise_beta` — Alembic **`003`** (no migration applied) |
| Deploy result | **DEPLOYED** 2026-10-20T12:45Z UTC. Backup: `/var/backups/fashionrise/web-v3a-deploy-20261020T124335Z` |

**WEB-V2.2 acceptance on production:**

| Check | Result |
|---|---|
| Desktop acceptance | **5 / 5 PASS** |
| Cross-device cloud recovery | **PASS** |
| Two-tab conflict resolution | **PASS** |
| Tablet portrait | Usable |
| Tablet landscape in a normal browser | **Limited.** Tabs and the address bar leave too little height, so the paper and side panels were cut off. WEB-V2.3 corrects this. |

**WEB-V2.3:** merged as PR [#12](https://github.com/perielad2-netizen/FashionRise/pull/12) at `f8a5b222`. Real-tablet acceptance 6/6 PASS. Report: `docs/WEB-V2.3-TABLET-LANDSCAPE-QA.md`

**WEB-V3A:** merged PR [#13](https://github.com/perielad2-netizen/FashionRise/pull/13) at `85b6561b` and deployed. Report: `docs/WEB-V3A-DESIGN-LIBRARY-QA.md`. Physical-device acceptance still pending.

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
| Current `main` | **`85b6561b`**, merge of PR #13 (WEB-V3A) |
| Production frontend / backend | **`85b6561b` / `85b6561b`** (deployed 2026-10-20T12:45Z UTC) |
| Unity Visual Reboot VR1 (draft PR #8) | **SUPERSEDED for active client** — not the product path; left open until PM closes |
| **WEB-1 / WEB-V2.1C** | **MERGED** to `main` as PR #9 (`6df327ba`) |
| **WEB-V2.2** | **MERGED** as PR #11 (`9db1fa86`) and previously deployed |
| **WEB-V2.3** | **MERGED** as PR #12 (`f8a5b222`). Tablet acceptance 6/6 PASS. Superseded in production by WEB-V3A. |
| **WEB-V3A** | **MERGED** PR #13 (`85b6561b`) and **DEPLOYED**. Operator physical-device acceptance **pending**. |
| INFRA-2 docs | Separate draft PR #10. Not part of the WEB-V3A branch. |
| Paid OpenAI | **NONE** |
| Persistent AI/backend behavior | **UNCHANGED** |
| Safety flags (prod) | Registration / AI / uploads / public docs / Gallery remain Nginx-denied. AOP `ssl_verify_client on`. Cloudflare Access unchanged. |

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

**WEB-V2 — functional Studio integration:**

- Approved shell on `/studio`; visual composition **approved**
- Report: `docs/WEB-V2-VISUAL-QA.md`

**WEB-V2.1 — private-beta draft persistence:**

- Debounced autosave to private `/api/v1/designs` working draft (`fashionrise.studio.draft.v1`)
- IndexedDB recovery + explicit conflict dialog
- Model switch confirmation; Brush panel overlay; Magic notice-only
- Docs: `docs/WEB-V2.1-PRIVATE-BETA.md`

**WEB-V2.1A — data-loss prevention:**

- Authoritative snapshot saves; IndexedDB-on-edit + honest status; 409 concurrency; create reconcile; custom uploads disabled

**WEB-V2.1C — conflict resolution final gate (this amendment):**

- Keep this device rebases onto a revision above the current server snapshot and saves with optimistic concurrency
- Another concurrent server update reopens the choice; no silent overwrite
- Use cloud draft replaces IndexedDB even when the cloud revision is lower; Saved only after that write succeeds
- Automatic cloud writes suspended while a conflict is open, including saves already queued behind the request that opened it
- Create/reconcile cannot report Saved when acknowledged content differs from the local document
- Next: PM review, then protected family-beta tablet testing on fashionrise.app
- Deploy still **not** performed in this PR

**WEB-V2.1B — final persistence hardening:**

- Monotonic IndexedDB writes (delayed cloud A cannot overwrite local B)
- Atomic Studio create via per-owner advisory lock; equal-rev different-content → 409; identical retries idempotent
- Studio updates require `expected_revision`; reject stale/non-advancing transitions; non-Studio stays compatible
- Fingerprint no-op returns last server-acked revision (not unsent local rev)
- Non-409 preferred PUT failures do not blind-reconcile/overwrite
- Live FastAPI + isolated Postgres concurrency/create regressions
- Remaining: private-beta access gating; **operator live tablet acceptance**
- Deploy target: **fashionrise.app** via Cloudflare + isolated VPS — **not enabled in this PR**

**WEB-V2.2 — premium UI, brand assets, beta honesty (merged as PR #11, deployed frontend `9db1fa86`):**

- Login uses the approved emblem and wordmark on a cream plate. Header uses the approved monogram plus a readable cream/pink wordmark.
- Library cards are derived from the existing artwork. Female edge matte removed. Originals kept.
- Beta tools that already worked stay wired. Unfinished controls are labeled Soon or Unavailable.
- Shortcuts B, E, and undo/redo now match the Settings list.
- Beta limitation notices render once under the workspace title, including at 1024px and below, and dismiss without opening Settings.
- Persistence, Magic API, uploads, registration, and infra were not changed.
- Report: `docs/WEB-V2.2-VISUAL-QA.md`

**WEB-V2.3 — tablet landscape fit and final UI refinements (merged as PR #12, `f8a5b222`):**

Changes (frontend only):

- **Short landscape:** `#root` uses `100dvh` and the shell pads by safe-area insets. Grid rows are `minmax(0, 1fr)`, so panels scroll inside their own column. The 3:4 paper is sized from available width and height (`min(100cqw, max width, 75cqh)`). Compact header, dock, notice, rail, and panel spacing apply only at `(min-width: 821px) and (max-height: 760px)`. The tool rail scrolls when it is taller than the paper column. Model cards no longer overlap in a short library.
- **Sidebar:** the cropped “Fashion is your superpower” promo card is removed. Navigation controls are unchanged.
- **Generate with AI:** one line with the Soon label, in a sticky footer inside the Settings panel. Still notice-only.
- **Desktop brush window:** removed, and the paper takes the reclaimed room. Brush size and opacity stay in Settings. At 1024px and below, the Brush dock opens a dismissible sheet (`BrushControls`, formerly `FloatingBrushPanel`).
- Portrait keeps the WEB-V2.2 layout. With the Models dock open on a phone, the paper now shrinks instead of running off-screen.
- No change to persistence, backend, database, Nginx, Cloudflare, AI, uploads, registration, or brand assets.

Correction measured in local Chrome at 100% zoom (offline notice showing):

| Viewport | WEB-V2.2 paper | WEB-V2.3 paper |
|---|---|---|
| 1024 × 550 | 346 × 461, bottom 208px below the viewport | 227 × 302, fully visible (260 × 346 with no notice) |
| 1024 × 700 | 346 × 461, bottom 58px below the viewport | 339 × 452, fully visible |
| 1180 × 600 | Fits, but the brush window and Generate with AI were below the viewport | 291 × 388; brush controls and Generate visible in Settings |
| 1440 × 900 | 345 × 460 plus floating brush window | 468 × 624, no floating window |

WEB-V2.3 was merged as PR #12 (`f8a5b222`) and passed real-tablet acceptance 6/6.

**WEB-V3A — Export, Save & My Designs (PR #13 merged at `85b6561b`, deployed 2026-10-20T12:45Z):**

What changed:

- **Export PNG** (More menu):
  - 768×1024 PNG rendered on the device from the authoritative document.
  - Cream paper, croquis reference (dimmed when Dim reference is on), and ink in original colours. The eraser never erases the reference. No UI chrome.
  - Safe filename `fashionrise-<title>-YYYY-MM-DD-HHMM.png`. Honest failures. The object URL is always revoked. No AI and no upload.
- **Save as design** (header button and More menu):
  - Dialog with a validated title (1–80 characters).
  - Stores an owner-private snapshot as a separate design record.
  - Success is shown only after the server acknowledges a matching snapshot. Retries cannot create duplicates; see the QA doc for the one small documented race. Offline never reports success.
  - The Studio working draft is untouched.
- **My Designs** (`/studio/designs`, sidebar item):
  - The working draft and saved designs are shown separately, with title, date, model, and a bounded on-device preview.
  - Loading, empty, error, damaged, and refresh states.
  - Titles are rendered as text. Owner-private. No Gallery or social features.
- **Open a saved design:**
  - Fresh fetch plus strict validation.
  - Never silently replaces unsaved edits: they must sync first (Retry save). A synced sketch needs an explicit "Replace and open".
  - Known draft id: writes the single working draft forward with the normal `expected_revision` check.
  - No known draft id: `createOnly` end-to-end (create, recover identical content, or conflict). No blocking list preflight before persistence.
  - Uncertain network/5xx errors say the server outcome could not be confirmed (they never claim the draft was unchanged). Retry stays safe and can acknowledge the draft created by the first attempt.
  - Undo history starts fresh, and refresh restores the opened sketch.
- Fix found in browser QA: the More menu now stays above workspace notices.
- **Safety amendments (after PM review):** empty-Studio reopen race closed (`createOnly` + backend create/reconcile 409 on different content); uncertain reopen messaging corrected; redundant clean-empty list preflight removed so lost create-only responses recover on retry.

**Working draft vs saved designs:**

| | Studio working draft | Saved design |
|---|---|---|
| Count per user | Exactly one (unchanged) | Any number |
| `design_data.schema` | `fashionrise.studio.draft.v1` | `fashionrise.saved_design.v1` (snapshot nested inside) |
| `metadata` marker | `draftKind: "studio_working_draft"` | `designKind: "saved_design"`, no `draftKind` |
| Writes | Autosave, `expected_revision` OCC, create reconcile | One plain create per save. Never updated or overwritten by the UI. |
| Visibility | Private | Private |

The backend's singleton logic only matches the working-draft marker or a top-level Studio schema, so saved designs never enter create-reconcile or revision checks. This is proven against live FastAPI and PostgreSQL in `backend/tests/test_saved_design_isolation.py`.

**Database / API / migration impact:** **no migration, no new endpoint, no schema change.**

- Reuses the authenticated `POST /api/v1/designs`, `GET /api/v1/designs/my`, `GET /api/v1/designs/{id}`, and the existing working-draft `PUT`.
- **Narrow backend change:** Studio create/reconcile now returns **409** when an existing working draft has **different content** (including at a higher incoming revision). Same-content retries stay idempotent; lower-revision retries still return the newer existing draft. No new public route. Alembic head stays `003`. No data backfill.
- `/api/v1/gallery` is not used.
- **Deploy note:** after merge, restart FastAPI so the create/reconcile change is live. No PostgreSQL migration.

**Safety flags and disabled features (unchanged):**

- No paid AI or OpenAI calls. Magic and Generate with AI stay notice-only.
- Persistent custom uploads stay disabled. Saved designs never store custom-reference images.
- Public registration stays off. Public Gallery and unrestricted API routing stay off.
- Home, Design Book, Discover, My Looks, and future rail tools stay disabled.
- **Production deploy (2026-10-20T12:45Z):** frontend release `/var/www/fashionrise/releases/85b6561b` + backend `85b6561b`; Nginx root switched atomically; only `fashionrise-api` restarted; Alembic remained `003`; no pip install; no data changes. Safety deny rules and AOP unchanged (Nginx diff was the root path only).

**Production verification (deploy engineer, not operator acceptance):**

| Check | Result |
|---|---|
| Frontend REVISION file | `85b6561b338e31c102d101c8d458a1624e7b9f29` |
| Backend HEAD | `85b6561b338e31c102d101c8d458a1624e7b9f29` |
| `127.0.0.1:8010/health` + `/ready` | **200** (`ok` / `ready`, database `ok`) |
| Designs without auth | **401** on design id / `auth/me`; POST `/designs` **401** |
| Register / Gallery / AI / uploads / docs / OpenAPI via origin | **403** (after AOP client cert); **400** without client cert |
| AOP | `ssl_verify_client on` still enforced |
| Paid AI | **None** issued |
| Neighbors | CureCompass, PickWise, synagogue-management API, nginx, postgresql **active** |
| Operator physical-device acceptance | **Pending** — not claimed |

**Known limitations:**

- A duplicate **Save as design** card is possible only if the original request is still being processed on the server when a retry's lookup runs. Accepted as a non-blocking beta limitation; server-side dedupe is deferred.
- If a reopen response is lost and the user refreshes instead of retrying, the normal conflict dialog may appear. The user chooses; nothing is lost. In-dialog errors now say the outcome is unconfirmed.
- Custom references are not saved.
- Saved designs cannot be renamed or deleted yet.
- `/designs/my` returns full rows. This is fine at beta scale.
- Physical-device / Cloudflare Access acceptance on real desktop and tablet is still to do.

**Do not:**

- Continue Unity UI / merge PR #8 as product
- Start WEB-V3B in this authorization window
- Activate Magic / public registration / persistent uploads / public Gallery
- Mix INFRA-2 PR #10 into WEB-V3A

---

## Suggested next steps

1. **Operator physical-device acceptance** on `https://fashionrise.app` (desktop + tablet): follow `docs/WEB-V3A-DESIGN-LIBRARY-QA.md` §9 — save, browse, open, export; cross-device; two-device conflict; offline retry; second-account isolation; confirm PWA/service worker refreshes to the new build.
2. After operator sign-off, PM may close the WEB-V3A deploy window.
3. PM decisions for a later milestone (not authorized now):
   - server-side save dedupe
   - rename and delete for saved designs
   - a paged summary list endpoint
4. Custom-reference uploads stay disabled until owner-private retrieval exists. Magic/backend connection comes later. Reconcile INFRA-2 PR #10 separately.

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
6. Pick work from **Suggested next steps**. WEB-V3A is **deployed**; next gate is **operator physical-device acceptance**. Do not start WEB-V3B or enable blocked features.

---

## WEB-V3A verification (draft PR #13)

| Gate | Result |
|------|--------|
| `npm test` | **Pass: 170 tests, 29 files.** Adds PNG export, save idempotency, format isolation, private filtering, previews, reopen without loss, `createOnly` race/refusal/recovery (including lost create-only response retry), uncertain reopen messaging, offline, switching with queued saves, cross-device conflict, and layout contracts. |
| `npm run lint` | Pass, with the same three pre-existing oxlint warnings |
| `npm run build` (`tsc -b` + Vite + PWA) | Pass |
| Backend focused suites | Studio concurrency + saved-design isolation: **15 / 15**. Full suite: 103 pass, 1 pre-existing unrelated failure (`test_cli_default_is_dry_run`). |
| Singleton rules | **Intact.** Saved designs never reconcile with the working draft. Different-content Studio create now 409s instead of overwriting. OCC update path unchanged. |
| Local browser full flow (**simulated**) | **33 / 33** original PASS. Safety amendment re-check **16 / 16 PASS** (create 409, fresh open, empty-open race, uncertain messaging + retry). Isolated `fashionrise_v3a_qa` DB only. |
| Production database | **Not used** |
| OpenAI / paid AI | **None** |
| Backend | Narrow create/reconcile change only. No migration. No infra. |
| Physical device | **Not yet** |

## WEB-V2.3 verification (PR #12, merged)

| Gate | Result |
|------|--------|
| `npm test` | **Pass: 87 tests, 24 files.** Adds landscape notices, brush access, Generate notice, orientation changes, sidebar, and a CSS layout contract. |
| `npm run lint` | Pass, with the same three pre-existing oxlint warnings |
| `npm run build` | Pass. Production CSS keeps `100dvh`, the container-unit paper sizing, and its fallback. |
| Browser matrix | **Pass** at 1024×550, 1180×600, 1024×700, 768×1024, 390×844, 1440×900, 1920×1080, on both the dev server and `vite preview` |
| Orientation / browser-chrome resize | **Pass.** Same canvas node, ink kept, Undo enabled. |
| Mouse, pen, and touch stroke placement | **Pass** (CDP-simulated pen and touch) |
| Desktop pixel diff vs WEB-V2.2 | Only the three approved changes: promo, Generate footer, paper area |
| OpenAI / paid AI | **None** |
| Backend / persistence / infra | **Unchanged** |
| Physical tablet | **Not yet.** Local headless Chrome only. |

---

## Changelog (handoff doc only)

| Date | Summary |
|------|---------|
| 2026-10-20 | **WEB-V3A final recovery fix (draft PR #13):** removed clean-empty list preflight that blocked same-content createOnly retry after a lost create response. 170 frontend tests. Still draft / not deployed. |
| 2026-10-20 | **WEB-V3A safety amendment (draft PR #13):** empty-Studio reopen uses `createOnly`; Studio create/reconcile 409s on different content (no silent overwrite); uncertain reopen messaging corrected. Focused backend 15/15; amendment browser 16/16. Still draft / not deployed. |
| 2026-10-20 | **WEB-V3A (draft PR #13, not deployed):** Export PNG; Save as design (private `fashionrise.saved_design.v1` records, idempotent retries); My Designs library with previews; safe reopen into the single working draft through OCC. Later amended for empty-open race + uncertain messaging. |
| 2026-10-20 | **WEB-V2.3 merged** as PR #12 (`f8a5b222`). Operator real-tablet acceptance 6/6. Deploy log not supplied, so verify the live frontend revision at the next deploy. |
| 2026-10-20 | **WEB-V2.3 (draft PR #12, not deployed):** short-landscape fit (`100dvh`, safe areas, height-aware 3:4 paper, constrained grid rows, compact chrome); sidebar promo removed; Generate with AI pinned in Settings; desktop floating brush window removed (dock sheet kept on tablets). 87 tests pass. Production stays frontend `9db1fa86` / backend `6df327ba`. |
| 2026-10-19 | **WEB-V2.2 deployed:** PR #11 merged at `9db1fa86`, then a web-only deploy. Desktop 5/5, cross-device recovery, and two-tab conflict PASS. Tablet portrait usable; landscape limited by browser chrome. |
| 2026-10-19 | **WEB-V2.2 notice visibility (`e547ab3c`):** Magic, Back, and header Settings messages render once under the workspace title at every width, including when Settings is hidden. Draft PR #11. Not deployed. |
| 2026-10-19 | **WEB-V2.2 UI polish (draft, not deployed):** brand crops, library-card cleanup, honest Soon states, wired shortcuts, responsive spacing. Production stays `6df327ba` on fashionrise.app. |
| 2026-10-19 | **Protected production:** operator confirmed login, sketching, and Saved on fashionrise.app at `6df327ba`. |
| 2026-10-19 | **WEB-V2.1C queued-autosave guard (PR #9, merged):** conflict check runs inside the queued save, before any API call. |
| 2026-10-19 | **WEB-V2.1C conflict resolution (PR #9):** Keep-device rebase + OCC; Use-cloud durable IDB replace; autosave paused during conflict; mismatched reconcile is not Saved. Still draft. Next = PM review → protected tablet beta. |
| 2026-10-19 | **WEB-V2.1A data-loss prevention (PR #9):** authoritative snapshot saves; IndexedDB-on-edit + honest status; `expected_revision`/409 concurrency; create reconcile; custom uploads disabled (not private). Live Postgres tests. Still draft. Next = PM review. |
| 2026-10-19 | **WEB-V2.1 private-beta persistence (PR #9):** designs API draft autosave + IndexedDB recovery/conflicts; custom upload; model-switch confirm; brush overlay; Magic still off. Still draft. Next = PM review + live tablet acceptance. |
| 2026-10-19 | **WEB-V2 functional Studio integration (PR #9):** approved shell promoted to `/studio` with real drawing/tools/models; design-lab retained DEV-only; Magic disabled. Visual composition later approved for WEB-V2.1. |
| 2026-10-19 | **WEB-V1 design-lab reconstruction (PR #9):** DEV-only `/_design/studio` full mockup visual prototype; production `/studio` preserved. Features in lab are not production. Visual direction later approved for WEB-V2. |
| 2026-10-19 | **WEB-1 final visual/asset integration (PR #9):** `uiAssets` registry + manifest; glyph/model cleanup; male croquis display asset; Unsaved session label; fashionrise.app noted (no deploy). Pointer preserved. Still draft. Next = PM/operator visual review. |
| 2026-10-18 | **WEB-1 drawing + asset pass (PR #9):** operator confirmed login/Studio and preferred the web look over Unity; pointer-up bug fixed; pencil retuned; FashionRise card/tool glyphs added. Still draft. Next = operator drawing retest. |
| 2026-10-18 | **WEB-1 pre-operator hardening (PR #9):** real login validation; export eraser ink-only; Pointer Events-only canvas; custom MIME validation. Draft/not merged. No backend/Unity/AI/paid calls. Next = operator Windows browser/PWA review. |
| 2026-10-18 | **WEB-1 web/PWA pivot:** Active client = `web-ui/` (Login → Studio). Unity marked LEGACY; PR #8 superseded for product path. Backend preserved. No paid AI. |
| 2026-10-18 | Prior Unity VR1 visual/asset notes remain historical under draft PR #8; not the active delivery path. |
| 2026-10-17 | Unity VR1 TMP / LayoutGroup / visual-fidelity amendments (historical). |
| 2026-05-12 … | Earlier Unity/backend milestones — see git history / prior rows in superseded handoffs. |
