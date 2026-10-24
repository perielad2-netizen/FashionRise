# FashionRise — project status & session handoff

**Purpose:** Single page to align **new chat sessions** and humans on **what exists**, **where it lives**, and **what to do next**.
**Maintenance:** After each meaningful milestone, update the **last updated** line, **milestone table**, and **suggested next steps**.

**Last updated:** 2026-10-24. **GitHub `main`:** **`350a3b7e`** (WEB-V4G PR #40 merged; includes PR #41 pose fidelity source **not deployed**). **Production frontend:** **`350a3b7e`**. **Production backend + AI worker:** **`2cbc1ad0`** · Alembic **`005`** · registration / Magic UI **on** · Nginx AI + fabrics allowlist **on** · standalone `fashionrise-ai-worker` · Access JWT **OFF** · `TRUST_PROXY_HEADERS` **OFF**. **WEB-V4F operator acceptance:** **5/5 PASS**. **WEB-V4G operator authenticated acceptance:** **5/5 PASS**. **Active draft:** **WEB-V4H** immersive drawing draft PR [#45](https://github.com/perielad2-netizen/FashionRise/pull/45) — PM hardening amendment (toolbar / Focus precedence / multitouch / artwork QA); see PR head for exact SHA. **Issue [#42](https://github.com/perielad2-netizen/FashionRise/issues/42)** Front/Back croquis: backlog after V4H. **Magic pose fidelity (Issue #39 / PR #41):** on `main`, production BE/worker unchanged, visual pose **NOT accepted**. Docs deploy checkpoint draft PR [#44](https://github.com/perielad2-netizen/FashionRise/pull/44) remains open — **do not auto-merge**. Cursor paid AI calls this run: **0**.

**Phase:** Protected family beta. WEB-V4G FE deployed + operator-accepted. Active engineering track is WEB-V4H immersive drawing (frontend-only draft). Magic pose-fidelity PR #41 remains GitHub-only.

**Production (`https://fashionrise.app`, behind Cloudflare Access + Authenticated Origin Pulls):**

| Layer | Revision |
|---|---|
| Frontend (`web-ui`) | **`350a3b7e…`** — Nginx root `/var/www/fashionrise/releases/350a3b7e`. `VITE_API_BASE_URL=/api/v1`, `VITE_REGISTRATION_UI_ENABLED=true`, `VITE_MAGIC_UI_ENABLED=true`. Permanent Workbox SW (no HTML precache / NavigationRoute). Legacy + 10 library croquis present. |
| Backend (FastAPI + PostgreSQL) | **`2cbc1ad0`** — `fashionrise-api` on `127.0.0.1:8010`; `AI_WORKER_ENABLED=false` (worker is standalone) |
| AI worker | Standalone `fashionrise-ai-worker` @ **`2cbc1ad0`** · `OPENAI_MODEL=gpt-6-luna` · `OPENAI_IMAGE_MODEL=gpt-image-1` · edit `max_retries=0` |
| Database | `fashionrise_beta` — Alembic **`005`** (unchanged) |
| Deploy backup | `/var/backups/fashionrise/v4g-fe-deploy-20261023T140541Z` (+ prior `v4f-fe-deploy-20261023T060542Z`) |

**Operator / Cursor VPS workflow:** Cursor already has authorized SSH (`FASHIONRISE_VPS_*`) and Git credentials for this host. Future PM assignments should authorize Cursor to run FashionRise-scoped VPS commands directly rather than asking the human to relay shell steps. Independent PM approval is still required for deploy, migrations, Nginx, Cloudflare, and secret handling. (Standing handoff also tracked in draft PR [#14](https://github.com/perielad2-netizen/FashionRise/pull/14).)

**WEB-V2.2 acceptance on production:**

| Check | Result |
|---|---|
| Desktop acceptance | **5 / 5 PASS** |
| Cross-device cloud recovery | **PASS** |
| Two-tab conflict resolution | **PASS** |
| Tablet portrait | Usable |
| Tablet landscape in a normal browser | **Limited.** Tabs and the address bar leave too little height, so the paper and side panels were cut off. WEB-V2.3 corrects this. |

**WEB-V2.3:** merged as PR [#12](https://github.com/perielad2-netizen/FashionRise/pull/12) at `f8a5b222`. Real-tablet acceptance 6/6 PASS. Report: `docs/WEB-V2.3-TABLET-LANDSCAPE-QA.md`

**WEB-V3A:** merged PR [#13](https://github.com/perielad2-netizen/FashionRise/pull/13) at `85b6561b` and deployed 2026-10-20T12:45Z. Report: `docs/WEB-V3A-DESIGN-LIBRARY-QA.md`. Deploy record: draft PR [#15](https://github.com/perielad2-netizen/FashionRise/pull/15).

**WEB-V3A operator-reported production acceptance** (recorded via PR #15; not independently reproduced by Cursor):

| Check | Result |
|---|---|
| Desktop draw → Save → My Designs → Open → Export PNG | **5 / 5 PASS** |
| Tablet / cross-device library, reopen, rotation, export | **4 / 4 PASS** |
| Offline Save → honest error → online Try again (one card) | **PASS** |
| Two-device draft conflict **detection** | **PASS** (detection only; both resolution choices not fully accepted) |
| Login/Studio recovery after temporary SW mitigation (“I'm in”) | **PASS** |

**Stage B operator browser acceptance:** **6 / 6 PASS** (valid Access: sign-in, Studio, drafts, My Designs, reopen, PNG Export — operator-confirmed). Cursor infrastructure probes (Access 302, AOP, SW hash, registration UI off) remain separately recorded in `docs/deploy/PWA-FRONTEND-ROLLOUT-STAGE-B.md`.

**Still outstanding for WEB-V3A / Access:** **expired** Cloudflare Access session check with the permanent SW; second-account privacy (needs registration activation); untested conflict-resolution branches (Keep device / Use cloud).

**WEB-V3B / registration:** **MERGED** PRs [#19](https://github.com/perielad2-netizen/FashionRise/pull/19)/[#20](https://github.com/perielad2-netizen/FashionRise/pull/20)/[#26](https://github.com/perielad2-netizen/FashionRise/pull/26). **Production activation PASS** (2026-10-21): backend `46747e85`, migration `004`, Nginx POST register allowlist, `REGISTRATION_ENABLED=true`, frontend Create Account on. **Real second-user browser acceptance PASS** (operator-confirmed 2026-10-21). Access/AOP unchanged. JWT/Option B hardening remains a **separate** optional track.

**WEB-V4A (Magic → React):** **MERGED** PR [#27](https://github.com/perielad2-netizen/FashionRise/pull/27) at `dc9e31aa` and **deployed**. React Studio uses Unity polish + poll/recovery; authenticated job image; `image_base64` redacted from job API; See last result after refresh. Production Magic UI on; Nginx AI allowlist live. **No paid generation yet** (operator deferred). Docs-only draft PR [#28](https://github.com/perielad2-netizen/FashionRise/pull/28) records activation — **do not merge as a deploy artifact**.

**WEB-V4B (Fashion design toolkit):** **MERGED** PR [#29](https://github.com/perielad2-netizen/FashionRise/pull/29) and **deployed** with V4C at `d7e37b59`.

**WEB-V4C (Custom fabric upload):** **MERGED** PR [#30](https://github.com/perielad2-netizen/FashionRise/pull/30) and **deployed** at `d7e37b59` / Alembic **`005`**. Private `fabric_assets` + owner-auth image route live.

**Production defect (2026-10-22) — fill autosave / Keep-this-device:** **Hotfix MERGED + backend deployed** at `c21fee6b` (now superseded by full `2cbc1ad0` stack). Operator may still need to choose **Keep this device** once in any leftover conflict UI.

**WEB-V4D + WEB-V4E production deploy (2026-10-22):** Authorized operator rollout of `main` **`2cbc1ad04e5bfc01d1d356c92398e26e3014afe9`**. Backend + worker + frontend switched; Alembic stayed **`005`**; **0** deploy-time paid OpenAI calls; AI queue had **0** non-terminal jobs before worker restart. Deploy detail recorded in docs-only draft PR [#36](https://github.com/perielad2-netizen/FashionRise/pull/36) — do not auto-merge as a deploy artifact.

**Post-deploy Magic operator sample:** Visual acceptance **PASS** for the first tested design (professional fashion illustration; creative concept preserved). Textile / fabric-pattern fidelity was **not exact**.

**Magic pose regression (Issue [#39](https://github.com/perielad2-netizen/FashionRise/issues/39), 2026-10-23):** Second sample — original asymmetric bent/lifted-leg croquis stance was reposed by Magic into a more conventional upright stance with both boots lowered. Professional WEB-V4E polish kept; **pose fidelity NOT accepted**. **PR #41 MERGED** to `main` @ `4819b951` (`pose_lock` + priority packing + anti-repose brief) — **not deployed** to production BE/worker. Detail: `docs/WEB-V4E-MAGIC-POSE-FIDELITY.md`.

**WEB-V4F:** **MERGED** PR #37 @ `1aa5dc5a` and **frontend-only deployed**. HSV picker + Magic contain + tablet Focus/materials. Backend/worker unchanged at `2cbc1ad0`. Operator authenticated acceptance **5/5 PASS**. Docs deploy record: draft PR [#38](https://github.com/perielad2-netizen/FashionRise/pull/38).

**WEB-V4G:** **MERGED** PR [#40](https://github.com/perielad2-netizen/FashionRise/pull/40) @ `350a3b7e` and **frontend-only deployed**. Operator authenticated acceptance **5/5 PASS** (numeric brushes + wheel, 16 gradients + custom designer, interactive closed custom-gradient fill, save/reopen/export, tablet Focus/materials/undo + legacy designs). Docs checkpoint: draft PR [#44](https://github.com/perielad2-netizen/FashionRise/pull/44).

**WEB-V4H (draft PR #45 — Issue #43):** Immersive full-screen drawing with real zoom/pan (Konva Layer transform + inverse pointer mapping), Fit Page / Fit Width / 100%, native Fullscreen API + fixed-viewport fallback, pinch / two-finger pan, Space+drag + Hand tool, Ctrl/Cmd+wheel zoom (Alt+wheel remains V4G brush size). Existing Focus mode preserved. **PM hardening amendment:** compact safe-area immersive toolbar (no horizontal clip; Exit always reachable; ≥44px tablet targets); immersive CSS wins over Focus at every breakpoint; real DrawingCanvas multitouch lifecycle + combined `pinchPan` anchor; touch Fill/Eyedropper commit on confirmed single-pointer up; artwork/paper QA with croquis. Frontend-only; no production changes in this PR.

**PWA / Cloudflare Access:** Stage B deployed permanent SW from PR [#16](https://github.com/perielad2-netizen/FashionRise/pull/16) at `8c6a391a`. No-session Access **302** verified; AOP **400** without client cert verified. Operator valid-session acceptance **6/6 PASS**. Expired Access **PENDING**.

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
| **Registration (2026-10-20)** | **Invite-only beta** (Cloudflare Access outer + application invitation inner). **Not** public registration. |

---

## Development integration

| Item | Status |
|------|--------|
| PR #1 Magic Look | **MERGED** — `433b1b99` |
| PR #6 GPT-6 Luna | **MERGED** — `a5b3c167` |
| PR #7 status docs | **MERGED** — `2fc4c1fa` |
| GitHub `main` | **`350a3b7e`** — WEB-V4G merged (PR #41 pose fidelity source present, BE not deployed) |
| Production frontend / backend / worker | **`350a3b7e` / `2cbc1ad0` / `2cbc1ad0`** · Alembic **`005`** |
| Unity Visual Reboot VR1 (draft PR #8) | **SUPERSEDED for active client** — not the product path; left open until PM closes |
| **WEB-1 / WEB-V2.1C** | **MERGED** to `main` as PR #9 (`6df327ba`) |
| **WEB-V2.2** | **MERGED** as PR #11 (`9db1fa86`) and previously deployed |
| **WEB-V2.3** | **MERGED** as PR #12 (`f8a5b222`). Tablet acceptance 6/6 PASS. |
| **WEB-V3A** | **MERGED** PR #13 (`85b6561b`) and **DEPLOYED**. Operator-reported desktop 5/5, tablet/cross-device 4/4, offline retry, conflict detection PASS (see above). |
| **WEB-V3B** | **MERGED** + **production registration activated** (PR #26 @ `46747e85`, Alembic `004`) |
| **WEB-V4A Magic React** | **MERGED** PR #27 @ `dc9e31aa` and **deployed** |
| **WEB-V4B Fashion toolkit** | **MERGED** PR #29 · **deployed** (now at `2cbc1ad0`) |
| **WEB-V4C Custom fabrics** | **MERGED** PR #30 · Alembic **`005`** |
| **Hotfix: fill autosave fingerprint** | **MERGED** PR #32 · included in `2cbc1ad0` |
| **WEB-V4D Studio UX + models** | **MERGED** PR #34 · **DEPLOYED** @ `2cbc1ad0` |
| **WEB-V4E Magic quality** | **MERGED** PR #35 · **DEPLOYED** backend/worker @ `2cbc1ad0` (edit `max_retries=0`; no generate fallback) |
| **WEB-V4F color picker + Magic preview** | **MERGED** PR #37 · **FE deployed** @ `1aa5dc5a` |
| **Magic pose fidelity (Issue #39)** | **MERGED** PR #41 @ `4819b951` — **not deployed**; visual pose **NOT accepted**; no paid validation |
| **WEB-V4G brushes + gradients** | **MERGED** PR #40 @ `350a3b7e` · **FE deployed** · operator **5/5 PASS** |
| **WEB-V4H immersive drawing (Issue #43)** | **Draft PR #45** — FE-only zoom/pan fullscreen + PM hardening amendment; **STOP for Technical PM final review** |
| **Issue #42 rear croquis / Front-Back** | **OPEN** — scheduled after V4H |
| PWA Access fix | **MERGED** PR [#16](https://github.com/perielad2-netizen/FashionRise/pull/16). Still in live SW assertions. |
| Registration UI gate | **MERGED** PR [#20](https://github.com/perielad2-netizen/FashionRise/pull/20). Production build **on** after activation. |
| Docs handoffs | Draft PRs [#14](https://github.com/perielad2-netizen/FashionRise/pull/14) (VPS workflow), [#15](https://github.com/perielad2-netizen/FashionRise/pull/15) (deploy record), [#28](https://github.com/perielad2-netizen/FashionRise/pull/28) (Magic activation), [#36](https://github.com/perielad2-netizen/FashionRise/pull/36) (V4D+V4E deploy record — do not auto-merge). |
| INFRA-2 docs | Separate draft PR #10. |
| Paid OpenAI | Post-deploy V4E sample visually accepted (textile imperfect). **Issue #39 pose sample NOT accepted.** PR #41 + V4G Cursor paid calls: **0** |
| Safety flags (prod) | Registration **on** (invite-gated). Magic AI allowlisted (polish + job/image only). Uploads / public docs / Gallery remain Nginx-denied. AOP on. Cloudflare Access unchanged. |

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

**WEB-V3A — Export, Save & My Designs (draft PR #13, not deployed):**

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
- No Cloudflare, Nginx, VPS, or production-data changes. No automatic deploy.
- Home, Design Book, Discover, My Looks, and future rail tools stay disabled.

**Known limitations:**

- A duplicate **Save as design** card is possible only if the original request is still being processed on the server when a retry's lookup runs. Accepted as a non-blocking beta limitation for this PR; server-side dedupe is deferred.
- If a reopen response is lost and the user refreshes instead of retrying, the normal conflict dialog may appear. The user chooses; nothing is lost. In-dialog errors now say the outcome is unconfirmed.
- Custom references are not saved.
- Saved designs cannot be renamed or deleted yet.
- `/designs/my` returns full rows. This is fine at beta scale.
- Tested only in local headless Chrome against an isolated database. Physical-device acceptance is still to do.

**Do not:**

- Continue Unity UI / merge PR #8 as product
- Merge or deploy WEB-V3A before PM approval
- Activate Magic / public registration / persistent uploads / public Gallery
- Mix INFRA-2 PR #10 into WEB-V3A

---

## Suggested next steps

1. **Exact next action:** Technical PM **final review** of WEB-V4H draft PR [#45](https://github.com/perielad2-netizen/FashionRise/pull/45) hardening amendment (Issue #43). **Do not merge or deploy** until authorized.
2. WEB-V4G production FE @ `350a3b7e`: operator authenticated acceptance **5/5 PASS** (done; unchanged).
3. After V4H acceptance: scope Issue [#42](https://github.com/perielad2-netizen/FashionRise/issues/42) Front/Back croquis as a separate draft PR (not in #45).
4. Magic pose fidelity PR #41 remains on `main` but **not deployed**. After separate authorize: deploy BE/worker → one paid Magic retest on Issue #39 sample.
5. **Do not auto-merge** docs draft PRs [#28](https://github.com/perielad2-netizen/FashionRise/pull/28)/[#36](https://github.com/perielad2-netizen/FashionRise/pull/36)/[#38](https://github.com/perielad2-netizen/FashionRise/pull/38)/[#44](https://github.com/perielad2-netizen/FashionRise/pull/44).
6. **Operator residual:** expired Access session test (still PENDING). Physical tablet / Apple Pencil multitouch+pressure validation for V4H still outstanding — emulated PointerEvents do **not** prove real Pencil behavior.

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
6. Pick work from **Suggested next steps**. WEB-V3A is deployed; WEB-V3B is on `main` but must not be activated in production yet; permanent PWA fix (PR #16) gates the next frontend deploy.

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

## WEB-V3B verification (draft PR #19, final safety corrections)

| Gate | Result |
|------|--------|
| Test DB safety | Fail-closed: missing `DATABASE_URL_TEST` → exit **2**; `fashionrise_beta` rejected; suites on `fashionrise_test` / `fashionrise_mig_v3b` only |
| Bound migration smoke | `run_migration_smoke.py` refuses missing/beta without connecting; `0→head` + `003↔004` on `fashionrise_mig_v3b` with ambient `DATABASE_URL` pointing at beta name — Alembic still bound to mig DB |
| Invite code-file | New-file only (`O_EXCL`/`O_NOFOLLOW`); existing/symlink refused; write failure revokes invite; secret never in stdout/stderr |
| Invite + concurrency pytest | **19 / 19 pass** |
| Full backend pytest | **145 pass**, 1 pre-existing unrelated fail (`test_cli_default_is_dry_run`) |
| `npm test` | **195 / 195 pass** (35 files) |
| `npm run lint` / `tsc` / `npm run build` | Pass (same 3 pre-existing oxlint warnings) |
| Rate-limit activation note | `TRUST_PROXY_HEADERS=true` only after Nginx overwrites `X-Real-IP` on **all** proxied API locations (login/refresh included); otherwise all users share `127.0.0.1` |
| Production DB / Nginx / CF / registration gate | **Untouched** |

## PWA Access fix verification (draft PR #16)

| Gate | Result |
|------|--------|
| Branch base | Rebased onto `main` `28449c41` (preserves WEB-V3B) |
| `navigateFallback` | Explicit `null` (no Workbox `NavigationRoute`) |
| HTML precache | Removed from `globPatterns`; `**/*.html` ignored |
| Standard `npm run build` | Runs `tsc` → `vite build` → **embedded** `assert-sw-access-safe` (fails closed). Standalone `npm run check:sw` kept for audits |
| Unsafe SW fixture red-path | `scripts/fixtures/unsafe-sw-with-html-navigation.js` → `check:sw` exit **1** |
| Frontend tests | **200 / 200** (includes SW safety + unsafe-fixture red-path) |
| Lint / tsc / build | Pass |
| Route smoke (Playwright + active SW) | `/login`, `/register`, `/studio`, `/studio/designs` — document navigations **not** served from SW (`fromServiceWorker=0`) |
| `REGISTRATION_ENABLED` default | **false** |
| Production deploy | **Not done** (draft only) |

## WEB-V4B verification (merged PR #29)

| Gate | Result |
|------|--------|
| Merge | **MERGED** @ `5a9440c0` (2026-10-22) |
| Production deploy | **Not done** — live still `dc9e31aa` |

## WEB-V4C verification (draft PR #30 — custom fabric upload)

| Gate | Result |
|------|--------|
| Head | Draft PR #30 on `cursor/web-v4c-custom-fabric-77c6` (amendment after PM review of `cd7681b7`) |
| Base | `5a9440c0` (required) |
| Private storage | Bytes under `local_storage_root/private_fabrics/` — **outside** `/static/uploads` mount; owner-auth `GET …/image` only; static path **404** |
| Account caches | `bindFabricCacheToUser` on login/logout/register/restore; generation guard drops in-flight; uploaded tile cache cleared |
| Pattern scale | Base tile **128px** × scale, clamp 24–512 → 0.25×=32, 1×=128, 4×=512 (no 512-saturation on 2048 uploads) |
| Image validation | `probe_image_dimensions` (PNG/JPEG/WebP headers) before `Image.open`/`load`; JPG/PNG/WebP + 8 MB / 2048 px preserved |
| Backend tests | Full suite **226 passed**; 1 unrelated fail (`test_cli_default_is_dry_run` branch-guard expects `cursor/openai-gpt6-luna-77c6`). Fabric suite **6/6** |
| Frontend tests | **266 / 266** (53 files); lint warnings only (pre-existing patterns); build + `check:sw` **ok=true** |
| Browser / demo | Real 2048 fabric on curved dress at 0.25×/1×/4×; save/reopen; PNG export; mock Magic capture (no paid call); A→B privacy (list empty, image 404, cache clear, static 404) |
| OpenAI / paid Magic | **None** |
| Nginx | Live `nginx -T`: **no** `/api/v1/fabrics` location (auth/designs/AI only). Proposal: `docs/deploy/PROPOSED-NGINX-FABRICS-ALLOWLIST.md` — **not applied** |
| Cloudflare / workers / Unity | **Unchanged** |
| Production | **Not deployed** — still Alembic `004` / FE `dc9e31aa` |
| Blocked operations | Merge, production deploy, Alembic `005` on prod, Nginx reload, paid Magic |
| Next action | **Technical PM final review of draft PR #30** → approve merge; separate auth later for migrate `005` + fabrics Nginx allowlist + FE deploy |

## Hotfix verification — fill fingerprint (draft PR [#32](https://github.com/perielad2-netizen/FashionRise/pull/32))

| Gate | Result |
|------|--------|
| Base | Production-approved `main` `d7e37b59` (Alembic **`005`**) |
| Root cause | `_studio_content_fingerprint` omitted `fills` → fill-only updates idempotent no-op → FE conflict / Keep-device Save failed |
| Correction | Normalized `fills` in fingerprint; missing ≡ `[]`; OCC / row locks / 409 / owner isolation preserved |
| Frontend | Inspected `draftPersistence` / `draftContentFingerprint` — already includes `fills`; **no FE change** |
| Focused BE | `tests/test_studio_draft_concurrency.py` **21/21** (fill-only solid/gradient/restyle/uploaded-fabric, idempotent, missing↔empty, 409, Keep-device rebase, create reconcile, cross-account) |
| Full BE | **236 passed**; 1 unrelated fail (`test_cli_default_is_dry_run` branch-guard expects `cursor/openai-gpt6-luna-77c6`) |
| Ruff | Changed test file clean; pre-existing `design_service` style debt untouched |
| FE checks | `draftDocument` + `draftPersistence` **21/21** |
| OpenAI / paid Magic | **None** |
| Production data | **Untouched** — no IndexedDB clear, no draft delete, no destructive migration |
| Blocked | Merge, production deploy of hotfix, Magic click |
| Next | **Technical PM review** → merge → backend-only deploy → operator Keep-this-device recovery |

## WEB-V4D+V4E production deploy verification (`2cbc1ad0`)

| Gate | Result |
|------|--------|
| Authorized SHA | `2cbc1ad04e5bfc01d1d356c92398e26e3014afe9` |
| Backup | `/var/backups/fashionrise/v4de-deploy-20261022T204254Z` · dump **1,520,125** bytes · `gzip -t` OK |
| AI queue before worker restart | **0** non-terminal jobs (`completed=9`) |
| Backend / worker | Checked out + restarted at `2cbc1ad0`; health/ready OK; imported code has `with_options(max_retries=0)` |
| Models / flags | `gpt-6-luna` / `gpt-image-1` / `AI_WORKER_ENABLED=false` / `REGISTRATION_ENABLED=true` preserved |
| Alembic | **`005` (head)** — no upgrade run |
| Frontend build | `npm test` **278/278** · lint 0 errors · `tsc -b`+vite build · `check:sw` **ok=true** |
| Frontend release | `/var/www/fashionrise/releases/2cbc1ad0` · 10 library PNGs + legacy female/male croquis |
| Nginx | FashionRise `root` switched only; `nginx -t` OK; reload OK; neighbors untouched |
| Deploy paid OpenAI | **0** (worker started; no completions/edits after restart) |
| Infra API smoke | `/health` ok · `/ready` ok · auth/designs/fabrics **401** unauth · register empty **422** · polish empty **401** |
| Signed-in Studio browser acceptance | **PARTIAL** — Magic sample visually accepted; broader Studio UX acceptance still outstanding |
| Paid Magic visual retest | **PASS** for tested design (textile-pattern fidelity not exact) |
| Rollback | App-only: checkout `c21fee6b` + nginx root `d7e37b59` (see backup in draft PR #36); DB restore not preferred |

Detail: docs-only draft PR [#36](https://github.com/perielad2-netizen/FashionRise/pull/36).

## Magic pose fidelity verification (Issue #39 — PR #41 MERGED, not deployed)

| Gate | Result |
|------|--------|
| GitHub | **MERGED** @ `4819b951` |
| Production BE/worker | Still **`2cbc1ad0`** — pose-fidelity code **not live** |
| Visual acceptance | **NOT accepted** — no paid validation authorized |
| Scope note | Backend Magic only; WEB-V4G must not modify `sketch_openai.py` |

## WEB-V4G verification (PR #40 — MERGED + FE deployed @ `350a3b7e`)

| Gate | Result |
|------|--------|
| GitHub / production FE | **MERGED** + **deployed** @ `350a3b7e` (`/var/www/fashionrise/releases/350a3b7e`) |
| Backend / worker / Alembic | Unchanged `2cbc1ad0` / `005` |
| Operator authenticated acceptance | **5/5 PASS** |
| Docs checkpoint | Draft PR [#44](https://github.com/perielad2-netizen/FashionRise/pull/44) — do not auto-merge |

## WEB-V4H verification (Issue #43 — immersive drawing draft PR #45)

| Gate | Result |
|------|--------|
| Scope | Frontend-only; no backend / worker / Nginx / Cloudflare / migrations / paid AI / production deploy |
| Base | `main` @ `350a3b7e` (WEB-V4G operator **5/5 PASS** on production FE) |
| Viewport architecture | Shared `viewportTransform` (absolute CSS-px/design-px scale + pan); Konva Stage fills host; content Layer applies scale/pan; `screenToDesign` inverse for all pointers |
| 100% | Absolute 1 design px = 1 CSS px |
| Fit modes | Fit Page · Fit Width (top-aligned when taller) · Center/Reset · Zoom ± · clamp limits keep Fit Width/100% attainable |
| Fullscreen | Native Fullscreen API from user gesture when available; fixed immersive CSS fallback otherwise; `fullscreenchange` tracked |
| Gestures (hardened) | Combined `pinchPan` (prev-mid design → next mid); second touch cancels draft + releases capture; window `pointerup/cancel/lostpointercapture` clears outside-stage pointers; cooldown never clears while residual pointers remain; touch Fill/Eyedropper commit on confirmed single-pointer up; Space+drag + Hand; Ctrl/Cmd+wheel zoom; **Alt+wheel reserved for V4G brush size** |
| Escape precedence | Modal → dock/sheet → immersive exit → Focus exit |
| Focus + immersive CSS | Immersive layout reasserted after narrow Focus `@media (max-width:820px)` and via trailing `.immersiveMode` / `.immersiveMode.focusMode` rules — Focus→Fullscreen→exit restores Focus |
| Toolbar (hardened) | Full-bleed safe-area two-row bar; Exit pinned; Pencil/Eraser/Fill/Hand/Undo/Redo + Zoom/Fit always reachable; measured **0 buttons outside viewport** at 768×1024 / 1024×768 / 390×844 / iPad Pro / short desktop; tablet targets **44px** (short-height desktop densifies to 40px) |
| Export / Magic capture | Viewport-only — design space remains **768×1024**; strokes/fills unchanged (no paid Magic invoked) |
| Frontend tests / lint / build / SW | Vitest **347/347** · oxlint warnings-only · `tsc -b` · production build · `check:sw` ok=true |
| Browser QA (new SHA) | DEV `/_design/studio-layout?v4gCustomFill=1` with real croquis + closed custom-gradient fill. Screenshots `/opt/cursor/artifacts/screenshots/v4h2-*`. Toolbar + Exit inside viewport on all tested sizes. Paper bounds: Mini portrait Fit Page ≈ **768×1024 @ 100%** (gain vs Focus paper ≈ **1.25×**); Mini landscape Fit Page **576×768 @ 75%**, Fit Width **133%**, zoom **≥200%** (311%). Pencil/eraser/eyedropper under zoom exercised. Focus preserved after immersive exit. |
| Physical stylus | **Not available** — emulated PointerEvents / Playwright touch flags do **not** prove Apple Pencil pressure or real device multitouch |
| Issue #42 | Backlog after V4H — **not** implemented in #45 |
| Paid OpenAI | **0** |
| Production | **Unchanged** — FE **`350a3b7e`** · BE+worker **`2cbc1ad0`** · Alembic **`005`** |
| Magic pose PR #41 | Merged on `main`, **not deployed**; visual pose **NOT accepted** |
| Docs PR #44 | Remains draft |
| Merge / deploy | **Blocked** — STOP for Technical PM **final** review |

## WEB-V4F verification (PR #37 — color picker + Magic preview + tablet layout; FE deployed)

| Gate | Result |
|------|--------|
| Scope | Frontend-only; no backend / worker / Nginx / AI / Magic prompts; **no WEB-V4G** brush/gradient features |
| Base | `main` @ `2cbc1ad0` (production baseline) |
| Color picker | Built-in HSV professional picker (SV square, hue, HEX/RGB sync, Apply/Cancel, portal modal) |
| Magic modal | Full-image `object-fit: contain`; notes collapsible; actions remain accessible |
| Tablet Focus bug (768×1024) | **Fixed** — `.focusMode .center` no longer overrides narrow one-column/two-row grid; paper keeps nonzero 3:4 box; single Exit Focus via dock |
| Tablet materials sheet | **Fixed** — fixed `min(48vh,420px)` sheet for Colors/Fabrics/Gradients; Done + opaque scrim; tab heights stable (420/420/420) |
| Compact thumbs | Gradients **64px** high (56–72 clamp), **4/row** on Mini sheet (≈744px panel); **2/row** in narrow panels/phones; fabrics capped **≤100px**; container-query density |
| Tall-tablet paper | Raised mid-width `--paper-max-w` (was 380px); iPad Pro 13 portrait paper ~524×699 (3:4) |
| CreatorWorkspace browser QA | DEV `/_design/studio-layout`: Focus + materials + measured thumb rects (Mini 4×64px gradients; mobile/desktop 2×64px; fabrics maxH 100) |
| Frontend tests | see latest PR head |
| Paid OpenAI during implementation | **0** |
| Operator authenticated acceptance | **5/5 PASS** |
| Merge / deploy | FE **deployed** @ `1aa5dc5a` (backend/worker unchanged) |
| Outstanding | WEB-V4G FE deployed + accepted; WEB-V4H draft active; Issue #42 backlog; Magic pose Issue #39 / PR #41 not deployed |

## Changelog (handoff doc only)

| Date | Summary |
|------|---------|
| 2026-10-24 | **WEB-V4H PR #45 PM hardening amendment:** tablet-safe immersive toolbar (measured inside viewport); immersive CSS precedence over Focus; DrawingCanvas multitouch lifecycle + `pinchPan`; touch Fill/Eyedropper deferral; croquis/paper artwork QA; Vitest **347**; **0 paid AI**; production unchanged (FE `350a3b7e` / BE+worker `2cbc1ad0`); WEB-V4G **5/5 PASS** recorded; **STOP for Technical PM final review**. |
| 2026-10-24 | **WEB-V4H draft (Issue #43):** immersive fullscreen drawing with shared viewport transform, Fit Page/Width/100%, pinch/pan, Fullscreen API + fallback; Focus preserved; Vitest 338; **0 paid AI**; production unchanged; **STOP for Technical PM review**. |
| 2026-10-23 | **WEB-V4G operator acceptance 5/5 PASS** + FE production @ `350a3b7e` (docs draft PR #44). |
| 2026-10-23 | **WEB-V4G PR #40 amendment (final):** reconcile onto `main` `4819b951` (PR #41 merged/not deployed); closed custom-gradient flood-fill proven (pressure-triple fixture fix; algorithm unchanged); CustomGradientDesigner keyboard/focus a11y + tests; brush persistence compat preserved; status preserves V4F **5/5 PASS** + pose **NOT accepted**; **0 paid AI**. |
| 2026-10-23 | **Magic pose fidelity PR #41 MERGED** @ `4819b951` (not deployed). |
| 2026-10-23 | **Magic pose fidelity PR #41 amendment:** priority pose-lock packing inside 3800-char budget (no mid-fact truncation); verbose vision regression tests; status doc corrects WEB-V4F **5/5 PASS** vs pose sample **NOT accepted**; full BE pytest/ruff/mypy reported; **0 paid AI**; **STOP for Technical PM final review**. |
| 2026-10-23 | **Magic pose fidelity (Issue #39, draft):** structured `pose_lock` + edit-brief anti-repose rules; offline pose tests + human rubric; WEB-V4E polish retained; models/edit policy unchanged; **0 paid AI**; **STOP for Technical PM review** (no deploy/worker restart). |
| 2026-10-23 | **WEB-V4F FE deploy recorded** @ `1aa5dc5a` (docs PR #38); backend/worker remain `2cbc1ad0`. |
| 2026-10-23 | **WEB-V4F PR #37 amendment:** compact gradient/fabric thumbnails via materials container queries (4-up on tablet sheet, 2-up narrow); measured CreatorWorkspace QA; **STOP for Technical PM review**. |
| 2026-10-23 | **WEB-V4F PR #37 amendment:** tablet Focus paper collapse + materials sheet height/scrim/Done + tall-tablet paper sizing; CreatorWorkspace layout QA; picker/Magic contain preserved; **STOP for Technical PM review**. |
| 2026-10-22 | **WEB-V4F draft:** professional color picker + Magic “Your Look” uncropped preview; status records V4D+V4E deploy @ `2cbc1ad0` and operator Magic visual PASS (textile fidelity imperfect); **STOP for Technical PM review** (no merge/deploy). |
| 2026-10-22 | **WEB-V4D+V4E production deploy SUCCESS** at `2cbc1ad0` (FE+BE+worker); Alembic `005`; backup `v4de-deploy-20261022T204254Z`; 0 deploy paid AI. Deploy record in draft PR #36. |
| 2026-10-22 | **WEB-V4E MERGED** PR #35 @ `2cbc1ad0` (includes SDK `max_retries=0` image-edit). |
| 2026-10-22 | **WEB-V4E SDK retry correction (draft PR #35):** image-edit uses `with_options(max_retries=0)`; chat/vision retries unchanged; offline tests assert one edit attempt. |
| 2026-10-22 | **WEB-V4E reconciled onto main after V4D merge:** PR #34 @ `3376827c` merged not deployed; PR #35 single-edit + sanitized logs; status doc conflicts resolved; **STOP for Technical PM final review.** |
| 2026-10-22 | **WEB-V4E PM corrections (draft PR #35):** single configured `images.edit` only (no mini fanout); sanitized provider log tokens; one-shot sketch decode; leak tests cover logs; first paid Magic technically OK / visually rejected. |
| 2026-10-22 | **WEB-V4D MERGED** PR #34 @ `3376827c` (not deployed). |
| 2026-10-22 | **WEB-V4D amendment:** legacy `female`/`male` restore original croquis geometry; new defaults `*-straight`; FE 278 tests; first paid Magic quality FAILED (tracked as WEB-V4E). |
| 2026-10-22 | **WEB-V4D Studio UX + model library (draft):** approved croquis replace built-ins; tabbed materials; focus canvas mode; unavailable placeholders removed; FE 272 tests; build/SW PASS; **no backend**. |
| 2026-10-22 | **Fill-autosave hotfix MERGED + backend deployed** PR #32 @ `c21fee6b` (FE still `d7e37b59`). |
| 2026-10-22 | **URGENT fill-autosave hotfix (draft):** production `d7e37b59`/Alembic `005` acceptance BLOCKED; fingerprint now includes fills; Keep-device path covered by API tests; no FE change; no paid Magic; **STOP for Technical PM review** (do not merge/deploy). |
| 2026-10-22 | **WEB-V4B+V4C production deploy** at `d7e37b59` / Alembic `005` (operator-authorized). Subsequent browser acceptance found fill-autosave defect. |
| 2026-10-22 | **WEB-V4C PM corrections (draft PR #30):** private `private_fabrics/` storage; account-scoped caches; fashion base-tile scale; header dim reject; Nginx fabrics allowlist doc (verified missing live; not applied); FE 266 / BE fabric 6/6; multi-scale + privacy demo. **STOP for final Technical PM review.** |
| 2026-10-22 | **WEB-V4C custom fabric upload (draft):** private `fabric_assets` + owner-auth image route; uploaded-fabric fills with scale; My Fabrics UI; Magic/export fail-closed; FE 262 tests; BE fabric suite 4/4. **STOP for Technical PM review.** No deploy / no Nginx / no paid Magic. |
| 2026-10-22 | **WEB-V4B MERGED** PR #29 @ `5a9440c0` (not deployed). |
| 2026-10-22 | **WEB-V4B final amendment (draft PR #29):** eyedropper `compositeFillAndInkLayers` (erase-over-fill samples fill); `checkPersistableFill` before editor state; focused + full FE tests/lint/build/SW. **STOP for Technical PM merge decision.** No Magic spend / no deploy. |
| 2026-10-22 | **WEB-V4B PM corrections (draft PR #29):** visible-ink fill barriers + erase/seam tests; composite eyedropper; fill/contour save limits without silent truncate; olive swatch fix; curved-dress acceptance PASS (255 tests). **STOP for Technical PM merge review.** No Magic spend / no deploy. |
| 2026-10-21 | **WEB-V4B fashion toolkit (draft):** functional fill/fabric/gradient/eyedropper; optional `fills[]` on draft/saved V1 schemas; shared Konva/PNG/Magic paint path; no paid Magic / no deploy. |
| 2026-10-21 | **WEB-V4A Magic production activation:** release `dc9e31aa`, worker + Nginx AI allowlist + Magic UI on; **0 paid generations**; operator deferred first browser Magic test until toolkit. Docs PR #28. |
| 2026-10-21 | **WEB-V4A Magic integration corrections (PR #27):** Nginx AI allowlist precedence; redact `image_base64` from job responses; See last result after refresh; fail closed on missing reference capture; overlapping Magic guarded. |
| 2026-10-21 | **WEB-V4A Magic → React:** reuse Unity polish + poll/recovery; `GET /ai/jobs/{id}/image` owner-auth; MagicLookPanel; merged + deployed at `dc9e31aa`. |
| 2026-10-21 | **Registration second-user browser acceptance PASS** (operator-confirmed). |
| 2026-10-21 | **Registration production activation PASS:** deploy `46747e85`, Alembic `004`, Nginx POST register, `REGISTRATION_ENABLED=true`, FE Create Account on. Access/AOP/neighbors OK. |
| 2026-10-20 | **Registration product polish:** distinct invite error copy; email-only `?email=` prefill (no invite token in URL); username charset aligned FE/BE; journey test (register→save→relogin→isolation); activation procedure `docs/deploy/REGISTRATION-ACTIVATION.md`. No production changes. |
| 2026-10-20 | **GitHub code merges:** PR #23 strict SlowAPI and PR #24 Access JWT merged to main; no VPS deploy, flags unchanged. PR #22 docs merge approved separately; Stage C and Stage D remain blocked. |
| 2026-10-20 | **PR #22 rebased** onto `main` `ef4c42c2` after PR #21 merge; Stage B 6/6 + expired PENDING preserved; Stage C still **BLOCKED**. |
| 2026-10-20 | **Stage C trust-boundary prep:** AOP dashboard confirm PENDING; N3 fail-closed chosen; invite parent 750/no symlink verified; JWT design doc added; Uvicorn proxy-headers peer rewrite documented; PR #23 SlowAPI tests expanded. Still **BLOCKED**. |
| 2026-10-20 | **Stage C security amendment:** custom AOP CA verified; Option B real_ip preferred; Access JWT gap documented; invite path → `/var/lib/fashionrise/invites/`; verdict **BLOCKED_PENDING_TRUST_BOUNDARY_VERIFICATION**. No prod changes. |
| 2026-10-20 | **Stage C WEB-V3B readiness (initial):** preflight PASS; migration smoke PASS; later amended after PM review (Option A rejected as primary). |
| 2026-10-20 | **Stage B operator acceptance 6/6 PASS** (valid Access). Expired Access session still pending. |
| 2026-10-20 | **Stage B PWA frontend deploy SUCCESS:** live root `/var/www/fashionrise/releases/8c6a391a`; permanent SW `a51964e6…`; backend/Alembic unchanged; registration still off. |
| 2026-10-20 | **Stage A PWA rollout preflight:** production verified at `85b6561b` + SW hotfix; `main=ceb10a4e`; staging build of gated SHA `c017fa68`; **BLOCKED** on draft PR #20 before Stage B. No production switch. |
| 2026-10-20 | **PWA Access final amendment (draft PR #16):** standard `npm run build` embeds SW Access check; WEB-V3A operator acceptance table corrected (desktop 5/5, tablet 4/4, offline, conflict detection). Later merged as `ceb10a4e`. |
| 2026-10-20 | **PWA Access permanent fix (draft PR #16):** rebased onto `main` `28449c41`; no HTML precache; `navigateFallback: null`; `check:sw` fail-closed; route smoke with SW controller. Stop for PM review. Not merged / not deployed. |
| 2026-10-20 | **WEB-V3B merged** to `main` as PR #19 (`28449c41`). Not deployed; registration remains off. |
| 2026-10-20 | **WEB-V3B final safety corrections (draft PR #19):** bound `run_migration_smoke.py` (Alembic cannot silently use `.env` prod); invite `--code-file` O_EXCL/no-symlink + revoke on delivery failure; rate-limit activation note for per-client login buckets. Later merged. |
| 2026-10-20 | **WEB-V3B security amendment (draft PR #19):** test-DB fail-closed; concurrent register IntegrityError→409; FOR UPDATE revoke; trusted rate-limit IP; Nginx POST-only proposal; secure `--code-file` invites; FE isolation/uncertain recovery. Stop for PM re-review. Not merged / not deployed. |
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
