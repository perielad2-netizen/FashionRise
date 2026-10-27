# FashionRise — project status & session handoff

**Purpose:** Single page to align **new chat sessions** and humans on **what exists**, **where it lives**, and **what to do next**.
**Maintenance:** After each meaningful milestone, update the **last updated** line, **milestone table**, and **suggested next steps**.

**Last updated:** 2026-10-27 (**Professional Tech Pack P0/P1 reliability fix** — BE branch `cursor/web-techpack-p0-reliability-be-77c6`. Owner acceptance PASS for Measurements & Details on FE `69b83c01`. PR #115 audit PM-accepted. **0 paid AI**. Deploy status pending verification.)

**Phase:** Protected family beta. Create Real Design Generate → Wait → Download unchanged. Editor accepted. Professional PDF reliability hardening in progress/landed on BE branch.

**Production (`https://fashionrise.app`, behind Cloudflare Access + Authenticated Origin Pulls):**

| Layer | Revision |
|---|---|
| Frontend (`web-ui`) | **`69b83c01`** — Nginx `current` → `releases/69b83c01` (PR #114 quiet autosave + PDF validity + Done race). **OWNER ACCEPTANCE PASS — 2026-10-27**. |
| Backend (FastAPI + PostgreSQL) | **`732bda9f`** pre-fix baseline · P0/P1 reliability fix pending deploy from this branch. Alembic **`011`** (no migration). |
| AI worker | Standalone `fashionrise-ai-worker` — loads same techpack_ai modules; restart required with API on deploy |
| Database | `fashionrise_beta` — Alembic **`011`** |
| Nginx | `root /var/www/fashionrise/current;` · CF Access + AOP unchanged |
| AI spend | Ceiling **`$15`**, max **`$8`/run**, **`$20`/user/day**. **This work: $0 paid AI.** |

## OWNER ACCEPTANCE PASS — 2026-10-27 (Measurements & Details)

Owner PASS on FE `69b83c01` for idle editor, Done save, reopen persistence, Generate-not-stale-Download after edit with existing Professional PDF.

## PR #115 Professional quality audit — PM accepted

Evidence-only audit (`docs/TECHPACK-PROFESSIONAL-QUALITY-AUDIT.md` on `cursor/techpack-quality-audit-77c6` / PR #115). Decision **NEEDS IMPROVEMENT**. This branch implements the approved P0/P1 reliability fixes without regenerating paid PDFs.

## Professional Tech Pack P0/P1 reliability fix (2026-10-27)

| Item | Detail |
|---|---|
| Branch / PR | `cursor/web-techpack-p0-reliability-be-77c6` (base production BE `732bda9f`) |
| Scope | Structure validation before paid generate; remove `pieces[0]` artifact fallback; fair image budget; structure repair invalidates Download; honest pattern `proposed_unverified`; PDF material/sleeve REVIEW |
| Workflow | Unchanged: **Generate AI PDF → Wait → Download PDF** |
| Migration | **None** (Alembic stays `011`) |
| Offline tests | `test_techpack_p0_reliability` + v3/v31/v2/provenance/autofill/api → **40 passed** (MockProfessionalProvider, $0) |
| Paid AI | **0** |
| Blocked | No paid Professional regeneration authorized |

### Exact next action (owner / PM)

1. Review BE PR for P0/P1 reliability.  
2. After deploy: hard-refresh FE `69b83c01`; open FR-D47D-class two-piece draft → confirm Generate (not stale one-piece Download) after structure repair; do **not** pay for a new Professional PDF unless explicitly authorized.  
3. Rollback: restore prior BE files from deploy backup and restart `fashionrise-api` + `fashionrise-ai-worker`.


## Prior production lineage notes

See earlier sections in git history / PR #115 audit for Professional PDF quality findings (FR-7182 / FR-D47D / FR-CF5A). Keep the audit document intact as historical evidence.

## Changelog (handoff doc only)

| Date | Summary |
|------|---------|
| 2026-10-26 | **Create Real Design mobile UX + provenance DEPLOYED** FE `5f519734` (PR [#98](https://github.com/perielad2-netizen/FashionRise/pull/98)) + BE `08b66ca2` (PR [#97](https://github.com/perielad2-netizen/FashionRise/pull/97)); Alembic `010` unchanged; Android Edit Measurements sheet; Stage 4 Basic vs Professional clarity; PDF Basic/No-AI labeling; smoke PASS (heuristic provenance, **0 paid**); backup `techpack-mobile-ux-deploy-20261026T201157Z`. Owner first paid AI test still pending. |
| 2026-10-26 | **Create Real Design V3 DEPLOYED** FE `75a8e8ca` (PR [#96](https://github.com/perielad2-netizen/FashionRise/pull/96)) + BE `5fd4b843` (PR [#95](https://github.com/perielad2-netizen/FashionRise/pull/95)); Alembic `010` `techpack_ai_artifacts`; Nginx artifacts image route; owner-allowlist AI gates ON (ceiling `$15`, max `$8`/run, `$20`/day); non-AI smoke PASS (heuristic `$0`, professional confirm only); mocked CI + FR-7182 fixture PDF; Dual Magic ON; **0 paid generate by Cursor**; backup `techpack-v3-deploy-20261026T190439Z`. Owner to run first live AI Professional test. No monetization. |
| 2026-10-26 | **Create Real Design V2 DEPLOYED** FE `e2416ed0` (PR [#94](https://github.com/perielad2-netizen/FashionRise/pull/94)) + BE `f2433513` (PR [#93](https://github.com/perielad2-netizen/FashionRise/pull/93)); Alembic `009` `techpack_ai_runs`; Nginx AI allowlist; multi-piece PDF + flats/schematics; smoke PASS (heuristic `$0`, paid AI 403); Dual Magic ON; **0 paid AI**; backup `techpack-v2-deploy-20261026T181418Z`. No monetization. |
| 2026-10-26 | **Create Real Design DEPLOYED** FE `3ef29bc4` (PR [#92](https://github.com/perielad2-netizen/FashionRise/pull/92)) + BE `b4a0976c` (PR [#91](https://github.com/perielad2-netizen/FashionRise/pull/91)); Alembic `008` techpack tables; Nginx techpacks allowlist; API smoke PASS (5-page DRAFT/UNVERIFIED PDF); Dual Magic ON; **0 paid AI**; backup `techpack-deploy-20261026T163802Z`. Stop — no monetization. |
| 2026-10-26 | **My Looks Delete DEPLOYED** FE `6be1cf2d` (PR [#90](https://github.com/perielad2-netizen/FashionRise/pull/90)) + BE `26a374d5` (PR [#89](https://github.com/perielad2-netizen/FashionRise/pull/89)); Alembic `007` tombstone; Nginx DELETE on looks `{uuid}`; API smoke PASS; Dual Magic ON; **0 paid AI**; backup `my-looks-delete-deploy-20261026T160605Z`. Next: owner browser Delete check; do not start #83 PDF. |
| 2026-10-26 | **My Looks DEPLOYED** FE `811ffc52` (PR [#88](https://github.com/perielad2-netizen/FashionRise/pull/88)) + BE `ba013fdf` (PR [#87](https://github.com/perielad2-netizen/FashionRise/pull/87)); Alembic `006` `magic_look_meta`; Nginx looks allowlist; API smoke PASS; Dual Magic ON; **0 paid AI**; backup `my-looks-deploy-20261026T151741Z`. |
| 2026-10-26 | **Issue #17 delete 404 hardening prepared** on PR [#86](https://github.com/perielad2-netizen/FashionRise/pull/86) (FE-only): no auto-success on DELETE 404; raw owner-id reconcile; Vitest + tsc + build PASS; production still `4095e0ac`/`108db149`; **STOP before deploy**. |
| 2026-10-26 | **Issue #17 Delete saved design DEPLOYED** FE `4095e0ac` + BE `108db149` (PRs [#86](https://github.com/perielad2-netizen/FashionRise/pull/86)/[#85](https://github.com/perielad2-netizen/FashionRise/pull/85)); saved-only DELETE + Nginx narrow allowlist; browser smoke PASS; Dual Magic ON; Alembic `005`; **0 paid AI**; backup `issue17-delete-saved-20261026T134249Z`. |
| 2026-10-26 | **Magic polish DEPLOYED** FE `ec0ad13a` + BE/worker `18344e6a` (PRs [#80](https://github.com/perielad2-netizen/FashionRise/pull/80)/[#81](https://github.com/perielad2-netizen/FashionRise/pull/81)); shared garment-spec color-authority serialization fix; one paid Dual gray/uneven-strap visual **PASS**; Dual Magic ON; Alembic `005`; backup `v4j-magic-polish-deploy-20261026T123621Z`. |
| 2026-10-26 | **Undo→autosave false conflict FIXED + FE deployed** @ `c99c2c86` (PR [#79](https://github.com/perielad2-netizen/FashionRise/pull/79)); BE/worker stay `c103ee8d`; Vitest 29/29 + Playwright Undo→Save Front/Back PASS + multi-tab PASS; **0 paid AI**. |
| 2026-10-25 | **WEB-V4J Front/Back CONDITIONAL GO executed:** FE `4589a62d` (PR #69 + `VITE_STUDIO_DUAL_MAGIC_ENABLED=false`) + Stage B BE `6b253cb5`; Dual Magic BE #70 **not** deployed; Alembic `005`; prod smoke PASS (Front/Back, save/reopen, 9 Back models, Front Magic preserved, Dual Magic gated); **0 paid AI**; disposable smoke account cleaned up. |
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
