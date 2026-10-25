# FashionRise — project status & session handoff

**Purpose:** Single page to align **new chat sessions** and humans on **what exists**, **where it lives**, and **what to do next**.
**Maintenance:** After each meaningful milestone, update the **last updated** line, **milestone table**, and **suggested next steps**.

**Last updated:** 2026-10-25. **GitHub `main`:** **`c6fc1eb8`**. **Production FE:** **`a740a9b7`**. **Production BE/worker:** **`12f7acdf…`** (maint tip: Sunburst + #59 identity + #64 coverage; **never deploy undeployed `main`/PR #41 packing**). Alembic **`005`**. **Closed / operator-accepted:** #39, #51, #59, #60, #64. **Issue #42 OPEN.** **WEB-V4J Stage A:** architecture PR [#67](https://github.com/perielad2-netizen/FashionRise/pull/67) **ACCEPTED** (DRAFT, not merge-authorized); prior PR #50 closed unmerged/superseded. **WEB-V4J Stage B:** draft PR [#68](https://github.com/perielad2-netizen/FashionRise/pull/68) on immutable base `cursor/maint-base-12f7acdf-77c6` — fingerprint + reject-on-downgrade + `clearBackIntent` + PM amendments (bidirectional kind-lock, saved advisory lock, unknown-schema family 422, full saved fingerprint); offline verified; **not deployed**. **WEB-V4J Stage C (backend):** dual Magic orchestration on branch `cursor/web-v4j-c-dual-magic-77c6` (draft PR [#70](https://github.com/perielad2-netizen/FashionRise/pull/70)) — mandatory `magic_operation_id` + per-side idempotency keys, required `shared_garment_spec`, revision/fingerprint binding, owner `pg_advisory_xact_lock`, `GET /ai/magic-operations/{id}/jobs`, identity `409` on key misuse; side-aware prompts; see `docs/deploy/WEB-V4J-C-DUAL-MAGIC-READY.md`; **not deployed**. Stage C rear **artwork** still **not generated/approved**. Stage D Front/Back UI **not implemented**. Cursor paid AI: **0**.

**Phase:** Protected family beta. WEB-V4J Stage B amended for Studio↔saved metadata kind integrity — awaiting Technical PM re-review. No FE Back UI. No rear PNG. No deploy. **Exact next PM decision:** re-review PR #68 → GO/HOLD merge&deploy (still no Stage C/D).

**Production (`https://fashionrise.app`, behind Cloudflare Access + Authenticated Origin Pulls):**

| Layer | Revision |
|---|---|
| Frontend (`web-ui`) | **`a740a9b7`** — Nginx root `/var/www/fashionrise/releases/a740a9b7`. Combined #51+#59+#60. `VITE_API_BASE_URL=/api/v1`, registration/Magic UI on. Permanent Workbox SW. |
| Backend (FastAPI + PostgreSQL) | **`12f7acdf…`** — `fashionrise-api` on `127.0.0.1:8010`; `AI_WORKER_ENABLED=false` (worker standalone). Maint lineage only. |
| AI worker | Standalone `fashionrise-ai-worker` @ **`12f7acdf…`** · Sunburst high · `1024x1536` · edit `max_retries=0` |
| Database | `fashionrise_beta` — Alembic **`005`** (V4J Stage B needs **no** migration) |
| Deploy backup | `/root/fashionrise-backups/p2-64-coverage-deploy-*` (+ prior #59/#60 coord backup) |

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

**WEB-V4H (MERGED PR #45 — Issue #43):** Immersive full-screen drawing with real zoom/pan (Konva Layer transform + inverse pointer mapping), Fit Page / Fit Width / 100%, native Fullscreen API + fixed-viewport fallback, pinch / two-finger pan, Space+drag + Hand tool, Ctrl/Cmd+wheel zoom (Alt+wheel remains V4G brush size). **MERGED + FE deployed** @ `4f332a62`. **Real-tablet operator acceptance: 7/7 PASS.** Focus was still present at merge; WEB-V4I retires it.

**WEB-V4I (MERGED PR #48 — Issue #47):** Frontend-only tablet UX polish: fit intact 3:4 paper via cqh; Models overlay gallery; Focus removed; Settings Magic Soon footer removed; Models a11y focus trap. **MERGED + FE deployed** @ `dfcaa609`.

**P1 #51 — Fullscreen Hand→Pencil:** **CLOSED** on GitHub. Fix is on `main` / production FE lineage (`c6fc1eb8` → Release B `a740a9b7`). Historical hotfix verification table below remains a snapshot from the draft era.

**P1 #59 — Magic croquis identity (DEPLOYED — acceptance PENDING):** Maint BE/worker `74537077` + FE Release A/B send/honor `input_data.reference_model_id`. Draft PR [#61](https://github.com/perielad2-netizen/FashionRise/pull/61) not merged. **Do not close** until operator Magic samples confirm male/female selection preserved.

**P1 #60 — Narrow fill:** **CLOSED** — operator real-device acceptance **3/3 PASS** on production FE Release B `a740a9b7`.

**P2 #64 — Adult swimwear/lingerie coverage fidelity (DRAFT PR #65 — not deployed):** Operator saw Magic invent unrequested white body-covering fabric on a covered adult swimwear sketch. Offline root cause: vision/edit prompts lacked a skin-vs-fabric coverage contract, while Magic capture composites the light croquis underlay (can be misread as opaque fabric). Maint-tip draft adds protected `COVERAGE FIDELITY` + non-photoreal illustration contracts (survive evidence bounding), coverage `design_identity` fields, incomplete-vision handling, and mocked two-stage request construction. **No paid visual proof.** Keep issue OPEN until operator acceptance after authorized maint BE/worker deploy.

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
| GitHub `main` | **`c6fc1eb8`** — includes #51 Hand→Pencil + prior Studio work (PR #41 pose fidelity source present, **BE not deployed**) |
| Production frontend / backend / worker | **`a740a9b7` / `74537077` / `74537077`** · Alembic **`005`** · Sunburst high |
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
| **WEB-V4H immersive drawing (Issue #43)** | **MERGED** PR #45 @ `4f332a62` · **FE deployed** · real-tablet operator **7/7 PASS** |
| **WEB-V4I tablet UX polish (Issue #47)** | **MERGED** PR #48 @ `dfcaa609` · **FE deployed** |
| **P1 #51 Hand→Pencil immersive** | **CLOSED** — on production FE lineage (`c6fc1eb8` → `a740a9b7`) |
| **P1 #59 Magic croquis identity** | **DEPLOYED** BE/worker `74537077` + FE Release B; PR [#61](https://github.com/perielad2-netizen/FashionRise/pull/61) open; **operator acceptance PENDING** |
| **P1 #60 Narrow fill** | **CLOSED** — operator real-device acceptance **3/3 PASS** on FE `a740a9b7` |
| **P2 #64 Swimwear/lingerie coverage** | **Draft PR [#65](https://github.com/perielad2-netizen/FashionRise/pull/65)** on maint tip — protected coverage + illustration contracts; **STOP for PM**; not deployed |
| **Issue #42 / WEB-V4J Front-Back** | **OPEN** — deferred; architecture draft PR #50 |
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

1. **Exact next action:** Technical PM **review** of WEB-V4J **Stage B** maint-lineage draft PR (`design_service` v2 fingerprint + reject-on-downgrade). Base tip `12f7acdf…`. **Do not merge/deploy** until authorized. See `docs/deploy/WEB-V4J-B-PERSISTENCE-READY.md`.
2. After Stage B accept + authorized BE deploy: begin **Stage C** rear croquis artwork from accepted specs (operator-held fronts; no shippable binaries until approval).
3. **Stage D** Front/Back Studio UI only after B deployed and C approved.
4. Stage A PR [#67](https://github.com/perielad2-netizen/FashionRise/pull/67) remains DRAFT (accepted content; not merge-authorized by Stage A review). **Never deploy GitHub `main` BE/worker** for V4J.
5. **Do not auto-merge** maint/feature docs PRs without explicit authorization.
6. **Operator residual:** expired Access session test (still PENDING).

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

## WEB-V4H verification (Issue #43 — MERGED PR #45 @ `4f332a62`)

| Gate | Result |
|------|--------|
| Scope | Frontend-only immersive drawing; merged + FE deployed |
| Base / production FE | `main` / production @ **`4f332a62`** |
| Operator real-tablet acceptance | **7/7 PASS** |
| Viewport architecture | Shared `viewportTransform` (absolute CSS-px/design-px scale + pan); Konva Stage fills host; content Layer applies scale/pan; `screenToDesign` inverse for all pointers |
| 100% | Absolute 1 design px = 1 CSS px |
| Fit modes | Fit Page · Fit Width (top-aligned when taller) · Center/Reset · Zoom ± · clamp limits keep Fit Width/100% attainable |
| Fullscreen | Native Fullscreen API from user gesture when available; fixed immersive CSS fallback otherwise; `fullscreenchange` tracked |
| Gestures (hardened) | Combined `pinchPan` (prev-mid design → next mid); second touch cancels draft + releases capture; window `pointerup/cancel/lostpointercapture` clears outside-stage pointers; cooldown never clears while residual pointers remain; touch Fill/Eyedropper commit on confirmed single-pointer up; Space+drag + Hand; Ctrl/Cmd+wheel zoom; **Alt+wheel reserved for V4G brush size** |
| Escape precedence (at merge) | Modal → dock/sheet → immersive exit → Focus exit |
| Toolbar (hardened) | Full-bleed safe-area two-row bar; Exit pinned; measured inside viewport on tablet/mobile/desktop |
| Export / Magic capture | Viewport-only — design space remains **768×1024** |
| Operator acceptance | **7/7 PASS** on real tablet |
| Paid OpenAI | **0** during V4H engineering |
| Production | FE **`4f332a62`** · BE+worker **`2cbc1ad0`** · Alembic **`005`** |
| Magic pose PR #41 | Merged on `main`, **not deployed**; visual pose **NOT accepted** |
| Docs PRs #44 / #46 | Remain draft — **do not auto-merge** |
| Follow-on | Focus retired in WEB-V4I (product decision) |

## P1 #51 Hand→Pencil hotfix verification

> **Historical snapshot** (draft/hotfix era). Issue #51 is now **CLOSED**; production FE is `a740a9b7` on the `c6fc1eb8` lineage. Rows below preserve the contemporaneous record.

| Gate | Result |
|------|--------|
| Issue | [#51](https://github.com/perielad2-netizen/FashionRise/issues/51) — Fullscreen Hand→Pencil stops drawing until reload |
| Severity | **P1** — primary immersive drawing broken after pan/zoom tool switch |
| Baseline | GitHub / production FE **`dfcaa609`** · BE+worker **`2cbc1ad0`** · Alembic **`005`** |
| Reproduction | Studio draw → Full Screen → Hand → pan + pinch zoom → Pencil → strokes ignored until refresh |
| Root cause | Window pointer `useEffect` deps included `pointFrom` (viewport-sensitive). Pan/pinch `setViewport` remounted the effect; cleanup **`clearTimeout(gestureCooldownTimer)`** without clearing **`gestureCooldown.current`**, permanently blocking `onPointerDown`. |
| Before evidence | New controlled-viewport Vitest cases **5 failed / 0 strokes** on `dfcaa609` after pinch→Pencil (cooldown stuck). |
| After evidence | Same cases **14/14 pass** after fix; Pencil commits strokes after Hand pan, pinch, cancel/lostcapture, outside release, tool hops (Erase/Fill/Eyedropper), repeated Hand/Pencil. |
| Fix | Stable window listeners (`immersive` only) via handler refs; cooldown timer cleared **only on unmount**; clear `panning` when leaving Hand. No arbitrary substitute timeouts; residual pinch fingers still cannot stroke. |
| Scope | Frontend-only; no BE/worker/Nginx/Cloudflare/migrations/schema/artwork/paid AI; no WEB-V4J Front/Back |
| Frontend gates | Vitest **362** · oxlint warnings-only · `tsc -b` · production build · `check:sw` ok (no HTML precache / NavigationRoute) |
| Browser QA | Playwright on DEV `/_design/studio-layout`: **Android 390×844 PASS** (Path 1→2 after Hand/pinch/zoom→Pencil; 2→3 after Eraser/Fill/Eyedropper hop); **iPad 1024×768 PASS** (same). Shots: `/opt/cursor/artifacts/screenshots/p1-51-{android,ipad}-*.png`. No real multitouch hardware / no production Access session. |
| Production | **Unchanged** — still FE **`dfcaa609`** until authorized FE-only rollout |
| Next action | Technical PM review → merge → authorize FE-only deploy → **operator real mobile/tablet acceptance** of Hand→Pencil recovery → then resume WEB-V4J |
| Merge / deploy | **Blocked** — STOP for Technical PM review |

## WEB-V4I verification (Issue #47 — MERGED PR #48 @ `dfcaa609`)

| Gate | Result |
|------|--------|
| Scope | Frontend-only; merged + FE deployed @ `dfcaa609` |
| Base | Was `main` @ **`4f332a62`** (WEB-V4H); now production FE **`dfcaa609`** |
| Task A — croquis fit | Normal Studio paper sized with `min(100cqw, …, calc(100cqh * 768 / 1024))` + matching `max-height`; 3:4 preserved. Emulated bounds: Mini portrait paper **600×800** in stage **750×842**; Mini landscape **477×636** in **934×648**; Pro portrait **640×853**; mobile **364×485**; short desktop **402×536**; desktop **560×747**. `paperFits=true`, `aspect≈0.75` on all seven viewports. |
| Task B — Models gallery | Root cause: inline `max-height: 220px` strip stole canvas height. Now overlay dialog (`data-dock-overlay`) with large cards; portrait bottom sheet (~72vh); landscape side drawer (`min(480px,56vw)`, 2-col cards ~**220×294**). Stage size unchanged when Models opens. Escape/Done/scrim dismiss. Desktop sidebar browsing preserved (>1024). |
| Task C — Focus removed | No Focus / Exit Focus controls; Full Screen Drawing enter/exit + immersive toolbar remain. Escape: modal → dock → immersive exit. |
| Task D — Settings Soon footer | `SettingsInspector` footer / `generateSoon` removed. Header Magic (env-gated Soon) intact. |
| A11y amendment | Models gallery: focus moves to **Done** on open; Tab/Shift+Tab trapped inside dialog; focus restored to Models trigger on Done / Escape / scrim. Model-switch `ConfirmDialog` keeps focus + Escape precedence (`modalOpen()` excludes dock overlays). Regression tests in `CreatorWorkspace.layout.test.tsx`. |
| Visual PM approval | Tasks A–D approved at **`aef499b6`**; a11y-only follow-up on same PR #48 |
| Frontend tests / lint / build / SW | Vitest suite · oxlint warnings-only · `tsc -b` · production build · `check:sw` ok=true (no HTML precache / NavigationRoute) — see latest PR head |
| Browser QA | DEV `/_design/studio-layout` headless Chrome measurements + screenshots under `/opt/cursor/artifacts/screenshots/v4i-*` (visual SHA). A11y covered by Vitest focus/trap/restore cases. |
| Limitations | Emulated viewports only — physical tablet confirmation after deploy. Konva croquis is canvas-drawn (no separate img rect); paper frame used as visible page bounds. iPad Pro landscape (1366×1024) uses desktop sidebar Models (by design). Drawing stroke/export regression covered by existing Vitest, not re-paid-AI. |
| Issue #42 | **Not** implemented |
| Paid OpenAI | **0** |
| Production | FE **`dfcaa609`** · BE+worker **`2cbc1ad0`** · Alembic **`005`** |
| Follow-on | P1 #51 Hand→Pencil hotfix (active) |

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
| Outstanding *(historical row)* | At write-time: Production FE `dfcaa609`; P1 #51 hotfix draft. **Current:** FE `a740a9b7`; #51/#60 CLOSED; #59/#64 OPEN; PR #41 not deployed |

## Changelog (handoff doc only)

| Date | Summary |
|------|---------|
| 2026-10-25 | **WEB-V4J Stage B PR [#68](https://github.com/perielad2-netizen/FashionRise/pull/68) kind-integrity amendment:** reject Studio metadata `designKind=saved_design` poisoning (409) and mixed-kind create (422); subsequent two-sided Studio edits still succeed; suite **32** + full BE pytest updated; Alembic `005`; **0 paid AI**; **STOP for re-review — no merge/deploy**. |
| 2026-10-25 | **WEB-V4J Stage B PR [#68](https://github.com/perielad2-netizen/FashionRise/pull/68) PM amendment:** stored saved-kind protection (no studio hijack); owner advisory lock on saved create; unknown `draft.*`/`saved_design.*` family versions → 422; full saved envelope fingerprint (`sourceRevision`/etc.); suite **30** + full BE pytest **387**; Alembic `005`; **0 paid AI**. |
| 2026-10-25 | **WEB-V4J Stage B draft PR [#68](https://github.com/perielad2-netizen/FashionRise/pull/68):** immutable base `cursor/maint-base-12f7acdf-77c6` @ `12f7acdf`; `design_service` v2 fingerprint + reject-on-downgrade + `clearBackIntent`; initial suite **23** / pytest **380**; Stage A PR #67 accepted; PR #50 closed unmerged; **0 paid AI**. |
| 2026-10-25 | **P2 #64 PR #65 amendment:** protect coverage + non-photoreal illustration instructions from evidence truncation (bound lower-priority vision prose only); incomplete/null/unknown/contradictory coverage mocks; two-stage `build_sketch_chat_request`→`images.edit` handoff for male/female; **0 paid AI**; production unchanged; **STOP for Technical PM review**. |
| 2026-10-25 | **P2 #64 coverage fidelity draft (maint tip):** vision + edit garment-coverage contract (`COVERAGE FIDELITY` + coverage `design_identity` fields); initial mocked regressions; full BE pytest **342**; **0 paid AI**; production unchanged (`a740a9b7` / `74537077` / `005`). Issue #60 **CLOSED** (operator 3/3 PASS). |
| 2026-10-25 | **Coordinated P1 #59+#60 production deploy SUCCESS:** BE/worker `74537077` (maint on `b800e53d`); FE Release A `c30dbc93` then Release B `a740a9b7` (identity+narrow fill); Alembic `005`; Sunburst high unchanged; Vitest A **379** / B **436**; BE pytest **331**; AI queue **0** non-terminal; **0** paid AI / **0** jobs created; backup `p1-59-60-coord-20261025T081941Z`. Report: `docs/deploy/P1-59-60-COORDINATED-PRODUCTION-DEPLOY.md`. |
| 2026-10-24 | **P1 #51 Hand→Pencil hotfix draft PR [#52](https://github.com/perielad2-netizen/FashionRise/pull/52):** root cause = viewport remount cleared gesture cooldown timer while flag stayed true; stable window listeners + unmount-only timer cleanup; Vitest **362** (8 new controlled-viewport regressions); Playwright Android/iPad PASS; lint/tsc/build/check:sw PASS; **0 paid AI**; production unchanged (`dfcaa609` / `2cbc1ad0` / `005`); **STOP for Technical PM review — no merge/deploy**. |
| 2026-10-24 | **WEB-V4I PR #48 MERGED + FE deployed** @ `dfcaa609`. |
| 2026-10-24 | **WEB-V4I PR #48 a11y amendment:** Models gallery focus-in (Done), Tab trap, restore Models trigger on Done/Escape/scrim; model-switch confirm precedence; Vitest a11y cases; visual Tasks A–D remain approved at `aef499b6`; **0 paid AI**; (superseded by merge/deploy above). |
| 2026-10-24 | **WEB-V4I draft PR #48 (Issue #47):** normal-Studio croquis cqh fit; Models overlay gallery (portrait sheet / landscape drawer); Focus retired; Settings Generate-with-AI Soon footer removed; Vitest **351**; browser measurements on 7 viewports; **0 paid AI**; production unchanged (FE `4f332a62` / BE+worker `2cbc1ad0`); PM visual approval at `aef499b6`. |
| 2026-10-24 | **WEB-V4H PR #45 MERGED + FE deployed** @ `4f332a62`; real-tablet operator acceptance **7/7 PASS**. |
| 2026-10-24 | **WEB-V4H PR #45 PM hardening amendment:** tablet-safe immersive toolbar (measured inside viewport); immersive CSS precedence over Focus; DrawingCanvas multitouch lifecycle + `pinchPan`; touch Fill/Eyedropper deferral; croquis/paper artwork QA; Vitest **347**; **0 paid AI**; (superseded by merge/deploy above). |
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
