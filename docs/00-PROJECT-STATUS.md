# FashionRise — project status & session handoff

**Purpose:** Single page to align **new chat sessions** and humans on **what exists**, **where it lives**, and **what to do next**.
**Maintenance:** After each meaningful milestone, update the **last updated** line, **milestone table**, and **suggested next steps**. Keep historical sections below as an archive — do not silently truncate milestones.

**Last updated:** 2026-11-05 (**Try On clip-frame** pending pin · prior **`448192c0`** · **0** agent paid calls.)

**Phase:** Protected family beta. Create My Croquis V5 unchanged. Studio drawing includes Professional Sketch Engine V1 with **Charcoal continuous ribbon V2** (Ink/Airbrush unchanged). Try On Person smart flow + pale bridal / footwear fixes unchanged on BE **`900bda6b`**.

**Production (`https://fashionrise.app`, behind Cloudflare Access + Authenticated Origin Pulls):**

| Layer | Revision |
|---|---|
| Frontend (`web-ui`) | **`448192c0`** — release `/var/www/fashionrise/releases/448192c0` · Try On shoe-frame soft pad + V2.6 footwear. FRONT_BACK/MAGIC/DUAL **ON**, REGISTRATION **OFF**.
| Backend (FastAPI + PostgreSQL) | tip **`448192c0`** · Try On **`v2.6`** footwear + soft-pad gate · Alembic **`015`**.
| AI worker | `fashionrise-ai-worker` · croquis **v5** unchanged |
| Database | `fashionrise_beta` — Alembic **`015`** (unchanged) |
| Nginx | photos `client_max_body_size` **25m** · FE `current` → **`448192c0`** |
| AI spend | **#175 unlock preserved**: ceiling **`$100000`** · per-run **`$1000`** · day **`$100000`** · max exposure **100000¢** · gens/day **OFF** · Max soft budget **100000**. |

## Fill flush under outline — LIVE FE (2026-11-05)

Bucket fill stopped short of visible ink because the flood barrier includes a 2px gap-close dilate (+ AA fringe). New fills expand under outline ink before contour persist so color meets the stroke (ink still paints on top). App **`0cb34bf1`**. Rollback `/var/backups/fashionrise/fill-flush-outline-*/ROLLBACK.sh` → **`0ec4d653`**. Re-tap Fill on older regions to refresh.

## Try On shade-erase paper-frame hem — LIVE FE (2026-11-05)

Shade eraser tips outside 768×1024 no longer flip garment capture to the extended-paper frame (which letterboxed fills and failed completeness with “lost lower parts”). `resolveExportFrame` ignores shade/highlight; Magic/Try On capture force `frame: 'legacy'` after the ink/fills gate. App **`b8c599b2`**. Rollback `/var/backups/fashionrise/tryon-paper-frame-*/ROLLBACK.sh` → **`d18ad628`**.

## Try On shade-bounds + Flip hide — LIVE FE (2026-11-05)

Shade/highlight eraser overshoot no longer blocks Try On Person capture; paper-corner Flip is hidden when no published rear croquis exists (My Croquis / personal). App **`d18ad628`** (PR #188). Rollback `/var/backups/fashionrise/tryon-flip-hotfix-*/ROLLBACK.sh` → **`70eb0fcd`**.

## Charcoal V3 pencil-tip — LIVE FE (2026-11-05)

Hard graphite tip/core with soft radial vanish and tip→tail lift. New strokes use `charcoalRenderer: 3`; V1/V2 saved strokes unchanged. Airbrush/Ink paint unchanged.
App **`7c44fbeb`**. Rollback `/var/backups/fashionrise/charcoal-v3-*/ROLLBACK.sh` → **`0739fbd2`**.

## Charcoal Shading V2 — LIVE FE (2026-11-05)

### Hotfix — false Draft recovery conflict (2026-11-05)
Selecting Charcoal/Airbrush then drawing opened **Draft recovery conflict**; **Keep this device** showed **Save failed**.
**Cause:** FE `draftContentFingerprint` only sorted top-level keys. Professional stroke fields (`garmentMask` / `charcoalRenderer`) changed insertion order after `parseStudioDraftDocument`, so PUT **200** extract ≠ send fingerprint → false conflict. BE already uses deep `sort_keys`.
**Fix:** deep-canonicalize nested objects in `draftContentFingerprint` (Python-equivalent). Ink/Airbrush paint unchanged.


### Root cause (V1 charcoal)
Stamp-based `paintCharcoal` used `stampCenters()` + overlapping radial gradients. Slow pointer motion stacked more dabs → darker blobs; edges looked like spray/smoke instead of fashion graphite.

### Fix
| Area | Change |
|---|---|
| Renderer | **Charcoal V2** — concentric full-path feathered ribbon mask → colorize once (`destination-in`) → single composite alpha. Density independent of sample rate. |
| Versioning | Stroke field `charcoalRenderer`: absent/`1` = legacy stamp (saved art), new charcoal = `2`. |
| Defaults | Charcoal size **18px**, flow **0.42**, softness **0.82**, texture **0.14**, multiply + Shadows + garment clip. Ink stays ~1.75px. Per-kind size memory. |
| Garment mask | Soft clip to fill alpha when enabled + fills exist; freehand otherwise. Does not alter fills. |
| Airbrush / Ink | **Unchanged** rendering. |
| Visual fixtures | Offline `@napi-rs/canvas` PNGs under `/opt/cursor/artifacts/charcoal-v2/` |

### Safety
| Field | Value |
|---|---|
| FE release | `/var/www/fashionrise/releases/0739fbd2` |
| Prior FE | **`3f196e9a`** (Charcoal V2) ← **`69ab52b4`** ← **`f8bc3b82`** |
| Rollback | `/var/backups/fashionrise/charcoal-draft-fp-*/ROLLBACK.sh` → **`3f196e9a`** |
| BE / Alembic / spend | unchanged |
| Agent paid AI calls | **0** |
| Tests | draft fingerprint charcoal regression + conflict/persistence suites pass; `tsc` clean |

### Owner acceptance (manual)
Hard-refresh until App SHA **`0739fbd2`**. Open a filled dress → select **Charcoal** → draw folds. Expect **no** Draft recovery conflict after save. Save status should settle to cloud-saved. Shade quality as Charcoal V2.

## Professional Sketch Engine V1 — LIVE FE (2026-11-05)

### Delivered
| Area | Change |
|---|---|
| Brushes | **A** tapered ink (perfect-freehand) · **B** charcoal (now V2 ribbon) · **C** soft airbrush |
| Layers | Logical **ink / shade / highlight**; shade·highlight erase does **not** punch base fills or croquis |
| Export / Magic | `paintInkStrokes` / `compositeFillAndInkLayers` composite the same shade→ink→highlight stack |
| Persistence | Optional stroke + brush-engine fields; legacy drafts open unchanged |
| UI | Brush picker with stroke previews; Layer chips; Advanced flow/softness/texture/blend |

### Safety
| Field | Value |
|---|---|
| FE release | superseded by Charcoal V2 above |
| Prior FE | **`ac3e219c`** ← **`900bda6b`** |
| Rollback | `/var/backups/fashionrise/sketch-engine-v1-*/ROLLBACK.sh` |
| BE / Alembic / spend | unchanged |
| Agent paid AI calls | **0** |
| Tests | `professionalBrushes` + export/draft/flood suite; `tsc --noEmit` clean |

### Owner acceptance (manual)
Outline with Ink → base fill → Airbrush shadows (Multiply) on Shadows layer → Charcoal folds → Highlights → erase Shadows only → undo/redo → save/reopen → Front/Back → Magic capture → mouse/stylus/tablet.

## #180 P0 Mobile Regression, Smart Failures & Recovery — LIVE (2026-11-02)

### Owner mobile evidence (Israel evening ≈ 19:44–19:47 UTC)
1. **Modal footer clipped** under Android Chrome / Samsung Internet bottom toolbar (`MagicLookPanel`).
2. **Green open-leg** Smart Try-On → spinner → truthful failure (no image).
3. **Green swimwear** Smart Try-On → same failure (no image). Save in My Looks untestable on new runs.

### Production job diagnosis (read-only; App `c3658dad`)
| Case | Primary job | Error | Stage | Prep / realism / Max | Structure guard | Spend |
|---|---|---|---|---|---|---|
| Open-leg (gfp `ada57815fdf2`) | `88701ff0…` (+ retry `0c0cbf86…`) | `PROVIDER_MODERATION_BLOCKED` / sexual | **output** | **none** | did not block | released · est. 40¢ · actual null · provider_called |
| Swimwear (gfp `017c981d1ecf`) | `97e372c3…` | same | **output** | **none** | did not block | same |

**Root cause:** #179 deliberately excluded **all** `PROVIDER_MODERATION_BLOCKED` from Max. Both owner failures were **OpenAI output-stage** moderation on the generated try-on pixels — not structure-guard false positives, not input moderation, not Max provider errors. Max never ran; **0** FASHN Max API calls for these ops.

**Product decision (#180):** Allow Max only when moderation stage is **`output`** (uploads accepted; Max uses independent prep→realism→Max and never replays blocked OpenAI pixels). **Input** moderation and `PROVIDER_OUTCOME_UNKNOWN` remain excluded.

### Fixes
| Area | Change |
|---|---|
| Mobile modal | `position:fixed` overlay · `svh`/`dvh` + safe-area · scrollable `panelBody` · sticky/flex footer always above chrome |
| Max eligibility | Output-moderation → Max; input-moderation / unknown → terminal |
| Smart recovery | `smart:` ops use Smart stage recovery (not dual Front/Back); Stop waiting copy truthful |
| Max idempotency | Canonical key `try_on:fashn_max:smart:{op}`; recover existing Max under spend lock; reconciliation-required blocks re-pay |
| Fidelity tests | Deterministic high-slit + swimsuit non–false-positive assertions (no conditional skips) |

### My Looks (no new paid calls)
Historical smart Max `ce83af19…` / `941b3a08…`: `get_look` OK · `image_available` · listed in My Looks · `experiment_excluded=false` · normal result (no experiment controls).

### Deployed
| Field | Value |
|---|---|
| App / FE / BE tip | **`513e2813`** (`513e28133d4271a21897adf8a8704fcf198aa87b`) |
| API / worker | restarted · `/health` ok · Alembic **`015`** |
| #175 spend env | verified unchanged |
| Max env | enabled + live unchanged |
| Rollback | `/var/backups/fashionrise/smart-tryon-180-20261102T201046Z/ROLLBACK.sh` → FE **`c3658dad`** |
| Agent paid calls | **0** |
| Prod pytest | `test_smart_tryon_harden_179` + `test_smart_tryon_openai_max_178` → **29 passed** |

### Hotfix — pale bridal OpenAI try-on lost cleavage/sleeve (2026-11-04) — LIVE `11cefc2b`
Owner peach gown (#F8F4F0): OpenAI `50f80224` filled deep V + dropped a sleeve. Root cause: pale fills vanish on white flatten (~5× less contrast). **Fix:** charcoal matte for OpenAI garment input only; prompt **`try-on-person-v2.2`**; upper geometry hints (pale / plunging V / both sleeves); FE skips outline `#111111` as solid fill.

### Hotfix — bikini bottoms false neckline blocked Max (2026-11-04) — LIVE BE `0b19625b`
Owner retest after sexual→Max: OpenAI input sexual → prepare OK → realism `0f887181` completed with **FIDELITY_NECKLINE_CHANGED on bottoms** (waist tip vs hips) → `block_fashn` → no Max. **Fix:** neckline gate skips `category=bottoms`; generative fidelity failures recover to local productize so Max can still enqueue.

### Hotfix — sexual/input moderation → garment→Max (2026-11-04) — LIVE `968a7838`
Owner: basic purple swimwear on new croquis was OpenAI **input** `sexual` — not our classifier inventing “sexual”. Product rule restored: moderation fail (input or output) → independent garment realism → Max. Prior #180 “output-only” gate left these on “did not finish”.

### Hotfix — Try On input safety messaging (2026-11-04) — LIVE FE `77b6837e`
Owner Smart Try-On on the new beach croquis failed twice (`dfac6af6`, `fe4adeb5`) with OpenAI **input**-stage `sexual` moderation. Max correctly stayed off (#180). UI had been showing generic “did not finish”. Now shows explicit safety-check guidance (try another croquis photo / simplify sketch).

### Hotfix — Create My Croquis silent Upload & Generate (2026-11-04) — LIVE FE `dd234423`
Owner mobile (Samsung, ~21:28 Israel): Upload & Generate disabled briefly then re-enabled with **no new croquis** and no visible error. Nginx access log: **`POST /api/v1/personal-croquis/photos` → 413** (phone JPEG >12m). Edge HTML 413 never became a FastAPI JSON detail, so the wizard showed nothing useful above the fold.
**Fix:** on-device compress/downscale under 8 MB before upload; Preparing/Uploading label on the primary button; clear 413 alert above the actions; nginx photos body limit **12m→25m**. Backup `/var/backups/fashionrise/croquis-upload-413-20261104T193657Z/ROLLBACK.sh`.

### Hotfix — silhouette lock Max enqueue (2026-11-03) — LIVE App `22bbf719`
Owner App `7169194f` retest (same green open-leg sketch): OpenAI output-mod → realism **locked** (`d0b6510c`, `structure_preserving_local`) → **POST /personal-try-on 422** “sketch-like garment plate” → “Did not finish”. Root cause: `decode_data_url_png` RGBA-re-encoded productize RGB back to the source-plate SHA, and sketch_prep shares the productize SHA. **Fix:** preserve original PNG bytes on decode; skip sketch-like SHA / soft fidelity when `structure_preserving_local`. BE-only deploy **`22bbf719`**.

### Hotfix — silhouette lock for open-leg dresses (2026-11-03)
Owner App `241ce14d` croquis-conditioned realism still reinvented the dress as a jumpsuit; fidelity passed because the product was mis-labeled high-slit. **Fix:** (1) detect photoreal jumpsuits with sustained dual columns; (2) when Studio geometry is a high-slit/open-leg dress, **skip generative realism** and lock the product plate to the Studio silhouette (`structure_preserving_local`); (3) if generative still runs and contradicts, recover to the locked plate instead of shipping pants. Total garment-type redesign is fail-closed.

### Hotfix — croquis-conditioned garment realism (2026-11-03)
OpenAI garment realism was inventing pants from open-leg dress plates because Studio context was only a downscale of the isolated garment (no figure). **Fix:** compose accepted personal croquis under the garment capture → Image 1 on-figure layer; Image 2 isolated plate for colors; prompt **v6** requires removing the croquis/figure from the product OUTPUT. Geometry/contradiction still use the isolated plate (figure legs must not false-trigger trousers).

### Hotfix — modal fit + open-leg dress→pants (2026-11-03) — LIVE App `995337ca`
Owner App `125a6a01` result: (1) Try On preview **CSS-cropped** head/hem in the modal — stage did not bound height so `object-fit:contain` could not shrink. Fixed: stage `max-height: min(64dvh, 640px)` + image `width/height 100%` contain. (2) Green open-leg dress still rendered as **pants via Max** because geometry never set `looks_like_high_slit_dress` (hints empty → realism/Max invented trouser legs). Fixed: open-leg detection no longer requires the trousers classifier first; owner fixture `b1bcbc86` asserts dress/slit hints + contradiction guard.
**Deployed:** FE/BE **`995337ca`** · backup `/var/backups/fashionrise/p0-180-modal-openleg-deploy-20261103T061902Z/ROLLBACK.sh` → FE **`ca11c33f`** · `/health` 200 · runtime fixture high_slit=True trousers=False · **0** agent paid calls.

### Hotfix — adults attestation (2026-11-03)
Owner morning retest on App `513e2813` failed in ~2s: **400** `Adults-only beta attestation…` (no AI job). Cause was the old **24h** `adults_beta` max-age, not Smart Try-On/Max.
**Product change:** adults-only confirmation is now **account-level for the current notice version** (`MY_CROQUIS_ADULTS_ATTESTATION_MAX_AGE_SECONDS=0`). No daily re-check after the checkbox. Re-attest only if the notice version/text changes. Preflight still reports `adults_attestation_valid`; Smart Try-On refreshes only when missing.

### Owner verify (STOP — owner paid visual tests only)
1. Hard-refresh until App tip **`22bbf719`** is live (Settings / health). FE build may still show **`7169194f`**.
2. Desktop + Samsung: Try On Person modal shows **full person** (head + hem) with footer actions visible — no CSS crop.
3. Same green open-leg dress sketch → OpenAI may output-mod; realism should **lock silhouette**; Max must **enqueue** (no “Did not finish” / sketch-like 422) and keep the open-leg dress (not pants).
4. Green swimwear → automatic Max on output-moderation when OpenAI refuses.
5. Ordinary closed dress OpenAI success → **no** Max.
6. Existing My Looks smart Max entries still list after reload.
7. Mid-run **Stop waiting** → Recover resumes the durable stage without a second paid start.

## #179 Unified Smart Try-On hardening — LIVE (2026-11-02)

### Owner evidence addressed
- Open-leg / slit dresses misread as trousers during garment realism (missing Studio geometry in realism `design_bits`).
- Smart Max results stamped `looks_eligible=true` / `experiment=false` were invisible in My Looks because `_experiment_lane_excluded` blanket-banned Max providers.
- Normal Smart Try-On leaked owner-experiment metadata (provider/prompt/cost/verdicts) when Max delivered the result.
- `Cancel wait` aborted polling only but sounded like a charge cancel.
- Client `smart_fallback=true` could authorize Max without server proof of a matching failed OpenAI primary; moderation refusals auto-routed to Max (#178) — now blocked.

### Fixes
| Area | Change |
|---|---|
| Garment structure | High-slit dress keeps `one_piece` prep; realism injects `openai_trouser_design_hints` from Studio context; dress↔trousers contradiction blocks FASHN (`STRUCTURE_CATEGORY_CONTRADICTION`) |
| Special silhouette | Narrow open-leg dress guidance only when geometry is confident (not ordinary garments) |
| My Looks | Smart public Max eligible; owner experiment / private / rejected stay out; Save verifies `GET /looks/{id}` before navigate |
| UX | Normal result = image + Compare / Download / Save / Back; experiment UI only when `experiment===true`; spinner unchanged; **Stop waiting** copy |
| Recovery | Persist smart operation + job ids; stop waiting does not cancel provider work |
| Max auth | `_authorize_smart_max_fallback` requires matching primary OpenAI job (user/croquis/fingerprint/revision/op id) + eligible technical failure; moderation / unknown excluded; duplicate Max recovered not regenerated |
| Billing | `user_visible_charge_units=1` remains metadata only — no fake debit system; #175 spend ceilings preserved (not public customer limits) |

### Deployed
| Field | Value |
|---|---|
| App / FE / BE tip | **`c3658dad`** (`c3658dadb530b20c444d76bb8430a291c85da398`) |
| API / worker | restarted · `/health` ok · preflight 401 unauth |
| Alembic | **`015`** unchanged (no migration) |
| #175 spend env | verified preserved |
| Max env | enabled + live unchanged |
| Rollback | `/var/backups/fashionrise/smart-tryon-179-20261102T192321Z/ROLLBACK.sh` → FE **`74623a58`** |
| Agent paid calls | **0** |

### Owner verify (STOP — owner may run paid paths; agent made none)
1. Hard-refresh until App **`c3658dad`**.
2. Ordinary closed dress / standard silhouette → Try On Person → OpenAI success unchanged (no Max).
3. Prior completed smart Max result → **Save in My Looks** → appears after refresh (jobs `ce83af19…` / `941b3a08…` should list).
4. Open-leg/slit green dress → realism should preserve dress+slit (or clean failure on contradiction) — do **not** expect auto-Max solely after OpenAI moderation.
5. Owner FASHN experiment lane still shows Accepted/Rejected; normal Smart result does **not**.
6. **Stop waiting** mid-generation → Recover later without a second paid start.

## #178 Smart Try On (OpenAI → Max Balanced 1k) — LIVE (2026-11-02)

### Design
1. User clicks **Try On Person** (one button).
2. OpenAI regular try-on runs first (existing path).
3. On terminal OpenAI failure (moderation / provider / timeout / failed), automatically:
   prepare plates → OpenAI realism → fidelity gate → auto-accept → **FASHN Try-On Max Balanced 1k**.
4. User sees only generic spinner **"Generating your try-on preview..."** then result or clean failure.
5. Owner experiment (manual v1.6 / Max / Accept / reuse) remains allowlist-gated and separate.

### Orchestration
Staged through existing async jobs in one FE modal lifecycle (not a single synchronous HTTP call). Shared `smart_operation_id` + `smart_pipeline` metadata for diagnostics. `user_visible_charge_units=1` — failed OpenAI reservations release on definite refusal; Max is the delivered try-on when fallback wins.

### Deployed
| Field | Value |
|---|---|
| App / FE / BE tip | **`74623a58`** (`74623a58e458078c0576c880d4d6d513849ed3bf`) |
| API / worker | restarted · `/health` ok |
| Alembic | **`015`** unchanged |
| #175 spend env | verified preserved |
| Max env | enabled + live unchanged |
| Rollback | `/var/backups/fashionrise/smart-tryon-178-*/ROLLBACK.sh` → FE **`55118842`** |
| Agent paid calls | **0** |

### Owner verify (STOP — owner may run paid paths; agent made none)
1. Hard-refresh until App **`74623a58`**.
2. Normal OpenAI success: filled ordinary garment → Try On Person → result without Max.
3. Fallback: design that OpenAI refuses → same button → spinner only → Max result (or clean failure if both fail). No Accept dialog / no provider names.
4. Owner experiment still available via **Owner FASHN experiment** when allowlisted.

## #177 Owner experiment activation fix — LIVE (2026-11-02)

### Symptom
Product Owner on App **`45221226`** saw only the normal FASHN v1.6 Accept flow — no **Owner experiment** section.

### Root cause (no secrets)
1. **Allowlist mismatch:** `FASHN_TRY_ON_MAX_OWNER_ALLOWLIST` matched a different older account, not the active try-on Product Owner (verified by email fingerprint only).
2. **Coupled gate:** FE showed the whole experiment panel only when `fashn_max_owner_allowed` was true, and that flag required allowlist **and** Max configured **and** Max live. Max flags were already `true` in prod — the allowlist miss was decisive; the coupled gate would still hide v1.6 experiment knobs if Max live were ever off.

### Fix
| Change | Detail |
|---|---|
| Preflight | `fashn_owner_experiment_allowed` = allowlist only; `fashn_max_owner_allowed` = allowlist ∧ Max configured ∧ Max live |
| FE | Panel when `owner_experiment_allowed`; Max radio selectable only when `max_owner_allowed`; otherwise explicit unavailable status |
| Cache | Clear Try On preflight / owner gates on account change; always refresh preflight on FASHN start |
| Prod allowlist | Appended active Product Owner email + username + uuid facets (idempotent; no PII logged) |
| Max flags | Unchanged — already `FASHN_TRY_ON_MAX_ENABLED=true` · `FASHN_TRY_ON_MAX_LIVE_HTTP=true` |

### Deployed
| Field | Value |
|---|---|
| App / FE / BE tip | **`55118842`** (`55118842a66f7601583b24a76be2dc057e3b7a38`) |
| API / worker | restarted · `/health` ok · preflight returns owner/Max gates |
| Alembic | **`015`** unchanged |
| #175 spend env | verified preserved |
| Max env | enabled + live unchanged; allowlist entry count increased |
| Rollback | `/var/backups/fashionrise/owner-experiment-177-*/ROLLBACK.sh` → FE **`45221226`** + prior BE files + prior allowlist |
| Agent paid calls | **0** |

### Owner verify (STOP — no agent paid generation)
1. Hard-refresh until App **`55118842`**.
2. Magic → FASHN Try On → **Owner experiment** visible with Reuse accepted / FASHN v1.6 / FASHN Try-On Max / Balanced·Quality / Max prompt.
3. First Max Balanced 1K: load accepted garment → select **FASHN Try-On Max** → **Balanced** · **1k** → Accept & Try On Max → mark verdict. Ordinary accounts must not see the section.

## #176 Try-On quality optimization + OpenAI refusal diagnosis — LIVE (2026-11-02)

### OpenAI refusal (≈18:20 Asia/Jerusalem)
| Job | UTC | Evidence |
|---|---|---|
| `d275a0b2-ab89-43fe-a3bf-9fadb55bc701` | 16:20:16 | `PROVIDER_MODERATION_BLOCKED` · stage **`output`** · categories **`["sexual"]`** · HTTP **400** · prompt **`try-on-person-v2.1`** · req `req_bb81704c…` |
| `c1a0be2a-ad0d-4afd-af3a-b496c8a0752b` | 16:17:35 | same pattern · req `req_a5967de4…` |

Request **reached OpenAI**. Hints were color/topology/upper-plane only — **no** high-slit dress geometry hints (continuous-fill dress; #174 slit classifier N/A). **Not** an input-image reject. No app defect to “fix” the provider block; FE/BE now show clearer **output** safety copy. Design preserved.

### FASHN v1.6 adapter vs docs
Confirmed: `tryon-v1.6` · `category` one-pieces (swimwear) · `garment_photo_type=flat-lay` · `segmentation_free=true` · `mode=balanced` · `moderation_level=permissive` · `num_samples=1` · `return_base64=true` · **no prompt field**.

### Owner Max visibility
Root cause: experiment panel required `hasRealistic` so Max/v1.6 controls were invisible before product generation. Fixed: show when `fashn_max_owner_allowed`; Accept still needs accepted product bytes.

### Owner comparison workflow
1. Reuse accepted realism job (exact product SHA / fingerprint / croquis bind) — no OpenAI regen.
2. Choose v1.6 or Max; set category/seg/mode/seed (v1.6) or Balanced/Quality 1k + prompt (Max).
3. Confirm estimate → one Try On → private result + Accepted/Rejected/Unreviewed.

### Deployed
| Field | Value |
|---|---|
| App / FE / BE tip | **`45221226`** (`45221226b98036f3c8f1c02d03cc210c5b83c43b`) |
| API / worker | restarted · `/health` ok · new routes return **401 Not authenticated** (reach FastAPI) |
| Alembic | **`015`** unchanged |
| #175 spend env | verified preserved |
| Rollback | `/var/backups/fashionrise/tryon-quality-176-*/ROLLBACK.sh` → FE **`1cf0e2b3`** + prior BE files |
| Agent paid calls | **0** |

### Owner verify (STOP — no agent paid generation)
1. Hard-refresh until App **`45221226`**.
2. Magic → FASHN Try On → owner experiment panel visible **before** Generate (v1.6 + Max).
3. Load an accepted garment (no OpenAI regen) → pick one of five comparison configs → Accept & Try On → mark verdict.
4. Optional: OpenAI Try On on filled green dress — if refused, expect clearer **output safety** copy; design unchanged.

## #175 Owner spend unlock — LIVE (2026-11-02)

### Symptom
Try On failed with: **“Max exposure exceeds per-run Create My Croquis spend limit.”**  
Cause: #173 raised `MY_CROQUIS_AI_MAX_EXPOSURE_CENTS` to **200** while `MY_CROQUIS_AI_MAX_USD_PER_RUN` stayed **$1.00** (100¢). Settled spend was only ~**$2.66** — not a real ceiling hit.

### Owner decision
Single-user beta — remove practical spend blocks (high positives; zero still fail-closes providers).

### Applied on VPS `.env` (API + worker restarted)
| Key | Value |
|---|---|
| `MY_CROQUIS_AI_SPEND_CEILING_USD` | `100000.00` |
| `MY_CROQUIS_AI_MAX_USD_PER_RUN` | `1000.00` |
| `MY_CROQUIS_AI_MAX_USD_PER_USER_DAY` | `100000.00` |
| `MY_CROQUIS_AI_MAX_EXPOSURE_CENTS` | `100000` |
| `MY_CROQUIS_AI_MAX_GENERATIONS_PER_USER_DAY` | `0` |
| `FASHN_TRY_ON_MAX_SOFT_BUDGET_CREDITS` | `100000` |
| `TECHPACK_AI_SPEND_CEILING_USD` / per-run / day | `100000` / `1000` / `100000` |

Rollback: `/var/backups/fashionrise/owner-spend-unlimited-175-*/ROLLBACK.sh`

### Owner verify
Retry the same Try On (no FE rebuild required). Spend-limit modal should not appear.

## #174 Open personal underlay + high-slit dress Try On — DEPLOYED (2026-11-02)

### Bugs
1. **Open from My Designs** with a personal-croquis save showed ink without the croquis underlay when the Studio pin was already the same id/version (`applyDocument` cleared the object URL; the load effect did not re-run).
2. **Regular OpenAI Try On** turned high-slit dresses into jumpsuit/pants. Image 2 is garment-only (no croquis pixels by design). Geometry mis-classified thigh-high slits as trousers and injected “jumpsuit — not a dress”; V2 also fought designed openings (“expose body beyond image 1”).

### Fix
1. FE: `personalUnderlayReloadToken` bumped in `applyDocument` and included in the personal underlay load effect deps.
2. BE: detect `looks_like_high_slit_dress` (connected hip + later asymmetric dual lobes) → dress/slit hints instead of trousers/jumpsuit.
3. Prompt **`try-on-person-v2.1`**: fashion slits/cutouts from image 2 are opaque garment styling; do not convert a slit dress into trousers/jumpsuit. No V3 swimwear wording.

### Deployed

| Field | Value |
|---|---|
| App / FE / BE tip | **`1cf0e2b3`** (`1cf0e2b3b8fcaf603448e56db66b6a0d28713965`) |
| API / worker | `fashionrise-api` + `fashionrise-ai-worker` restarted · `/health` ok |
| Alembic | **`015`** unchanged |
| Rollback | `/var/backups/fashionrise/underlay-dress-174-*/ROLLBACK.sh` → FE **`751840fb`** + prior BE files |

### Owner verify (STOP — no agent paid Try On)
1. Hard-refresh until App **`1cf0e2b3`**.
2. My Designs → Open **green leg open dress** (or any My Croquis save) → croquis underlay must appear; Models shows Active on Create My Croquis.
3. Regular Try On on the high-slit green dress — expect dress + slit, not pants/jumpsuit (owner-paid only).

## #173 Owner-only FASHN Try-On Max experimental lane — DEPLOYED (2026-11-02)

### Product decision
Owner-authorized paid model evaluation. Soft budget ~**90** FASHN credits. Compare **v1.6** vs **Try-On Max** on the same accepted realistic garment + person photo. Do not auto-accept Max results into My Looks.

### Implementation
1. New adapter `fashn_try_on_max_provider.py` — documented Max schema only (`product_image`, `generation_mode`, `resolution`, `prompt`, `seed`, `num_images`, `return_base64`).
2. Provider `fashn_max` reuses Accept + frozen `approved_garment_pieces` (no OpenAI garment regeneration).
3. Server owner allowlist `FASHN_TRY_ON_MAX_OWNER_ALLOWLIST` (empty = nobody). FE gated by preflight `fashn_max_owner_allowed`.
4. Defaults: Balanced · 1k · seed 42 · outputs 1 · fixed/editable experiment prompt.
5. Results stamp `experiment=true`, `looks_eligible=false` — excluded from My Looks gallery.
6. v1.6 adapter / OpenAI Try On / Fashion Magic / Accept nginx path unchanged.

### Deployed

| Field | Value |
|---|---|
| App / FE / BE tip | **`751840fb`** (`751840fbeb887ca9ac3ab4b274469f1aaba38c58`) |
| API / worker | `fashionrise-api` + `fashionrise-ai-worker` restarted · `/health` ok |
| Alembic | **`015`** unchanged |
| Max flags | `FASHN_TRY_ON_MAX_ENABLED=true` · `LIVE_HTTP=true` · owner allowlist armed |
| Soft budget | 90 credits · spend ceiling raised to **$15** for evaluation (was $5) |
| Provider calls during impl | **0** |
| Rollback | `/var/backups/fashionrise/fashn-tryon-max-exp-173-*/ROLLBACK.sh` → FE **`c0e2cb8d`** + prior BE/env |

### Owner test
1. Hard-refresh until App **`751840fb`**.
2. Personal croquis → Magic → FASHN Try On → generate/accept realistic garment (reuse existing Accept if still open).
3. Owner experiment panel appears: choose **FASHN v1.6** or **Try-On Max** (Balanced default or Quality; 1k default).
4. Tap **Accept & Try On** / **Accept & Try On Max (balanced|quality)**. Soft credit estimate is in the confirmation copy.
5. Results are private comparison only — not My Looks.

---

## My Designs personal croquis thumbnails — DEPLOYED (2026-11-02)

### Defect
My Designs cards for `model=personal` (and the Studio working-draft card) rendered garment ink only — no My Croquis underlay. Stock Female/Male library croquis still composited correctly.

### Root cause
`previewReferenceUrl` / `renderPreviewBlob` only resolved static `canvasSrcForModel` assets. `personal` returns `null` there; authenticated underlay fetch was Studio-only. Working-draft props also omitted `personalCroquisId` / `personalCroquisVersion`.

### Correction
1. `resolvePreviewReferenceUrl` loads the exact pinned personal version asset via `getPersonalCroquisVersion` + owner-bound cache (same path as Studio).
2. `PreviewRenderer` carries `ownerId` into thumbnail renders.
3. My Designs working-draft card passes personal pins through the preview key/snapshot.
4. Fail-soft: missing pin / erased asset → ink-only thumbnail (no throw).

### Deployed

| Field | Value |
|---|---|
| App / FE | **`c0e2cb8d`** (`c0e2cb8d8ba6d1dd2024bc252a9bcabacf2a58bb`) |
| BE / worker / Alembic | Unchanged (`071ea03d` stack + Alembic **`015`**) |
| Nginx FE root | `/var/www/fashionrise/current` → **`c0e2cb8d`** |
| Provider calls | **0** |
| Rollback | `/var/backups/fashionrise/my-designs-personal-preview-20261102T153344Z/ROLLBACK.sh` → FE **`071ea03d`** |

### Owner next
Hard-refresh until App **`c0e2cb8d`**. Open My Designs — “green leg open dress” and Current sketch (My Croquis) should show the body underlay like stock Female/Male cards. No re-save required for already-saved personal designs (pins were already stored).

---

## #172 P0 Final structure-review hardening — DEPLOYED (2026-11-02)

### Defect (Technical PM on #171)

`classify_structure_image_role()` could still label a legitimate full-body try-on photo as `isolated_garment` when the background is mostly white, clothing is dark, or little skin is recognized. That allowed plate geometry comparison to falsely fail (or soft-pass) a paid OpenAI Try On.

### Correction

1. OpenAI Try On completion stamps trusted server provenance `result_kind=openai_try_on_photo`.
2. Structure review **v3** never authorizes garment-mask comparison from white-bg / skin / opacity heuristics on those outputs.
3. Clear non-trouser source → `not_applicable`; clear trouser/jumpsuit source → `inconclusive` until garment-region isolation exists. No false structural failure; no fidelity certificate on the photograph.
4. Trusted isolated plate↔plate comparisons preserved (`result_kind` / `source_kind` = `isolated_garment_plate`).
5. Narrow 8-hint budget priority: trouser/jumpsuit geometry hints win over lower-priority color/print hints (FE + BE). V2 prompt unchanged.
6. Ordinary completed concept previews unchanged; FASHN Accept / nginx / capture safeguards preserved.

### Deployed

| Field | Value |
|---|---|
| App / FE / BE / worker SHA | **`071ea03d5c1f2e05d7d2ac6a713fb293fc9662a0`** (App **`071ea03d`**) |
| Alembic | **`015`** (unchanged) |
| Nginx Accept | Unchanged allowlist |
| Nginx FE root | **Fixed 2026-11-02 15:02 UTC** — live TLS `root` was still hardcoded to **`28bc5e8d`** (localhost API). Now **`/var/www/fashionrise/current` → `071ea03d`**. Backup `/var/backups/fashionrise/p0-172-nginx-root-fix-20261102T150208Z/` |
| Nginx allowlist | **Restored 2026-11-02 15:06 UTC** — truncated TLS config had dropped Looks/Croquis/Techpacks/cf-access allowlists; reload exposed 403s. Restored from #170 backup + Accept regex. Backup `/var/backups/fashionrise/p0-172-nginx-allowlist-restore-20261102T150630Z/` |
| Provider calls | **0** |
| Rollback | `/var/backups/fashionrise/p0-172-structure-harden-deploy-20261102T141257Z/ROLLBACK.sh` → FE **`e176f464`** |

### Remaining limitation

Automated fidelity still cannot certify OpenAI try-on photographs without garment-region isolation. No paid vision/segmentation added. Soft plate checks remain diagnostic only for trusted isolated plates.

### Owner next

**STOP before paid owner tests.** After hard-refresh to App **`071ea03d`**, owner may later re-test ordinary OpenAI Try On and green jumpsuit — expect normal `completed` preview (never false `completed_unverified` from white-bg photo pixels).

## #171 P0 Post-generation fidelity review correction — DEPLOYED (2026-11-02)

### Defect (Technical PM on #170)

`soft_try_on_structure_review()` treated full photoreal person images like isolated garment masks, and returned `unverified` for every non-trouser source — so ordinary tops/shorts/dresses became `completed_unverified`.

### Correction

1. Classify result images as isolated garment vs full scene; person photos → **`inconclusive`** (no pass/fail from skin/body/hair/background).
2. Non-trouser sources → **`not_applicable`** — ordinary OpenAI Try On stays **`completed`** with concept-preview disclaimers.
3. Only like-for-like isolated plate mismatches → **`failed`** / `fidelity_ok=false` / visible banner / excluded from My Looks gallery.
4. Additive trouser hints from Studio garment geometry preserved; **`try-on-person-v2`** base prompt unchanged.
5. #170 nginx Accept allowlist re-verified: direct API Accept probe → **401 Not authenticated** (reaches FastAPI, not edge 403). Prior owner Accept failures still **0 FASHN** credits; two realism attempts separately settled.

### Deployed

| Field | Value |
|---|---|
| App / FE / BE / worker SHA | **`e176f464478a3012534f1bb9bfd09de71e0a3a26`** (App **`e176f464`**) |
| Alembic | **`015`** (unchanged) |
| Nginx Accept | Still allowlisted; direct probe **401** (app), not edge 403 |
| Provider calls | **0** |
| Rollback | `/var/backups/fashionrise/p0-171-fidelity-review-deploy-*/ROLLBACK.sh` → FE **`dcee9eac`** |

### Remaining limitation

Automated fidelity cannot certify OpenAI try-on photographs without garment-region isolation. No paid vision/segmentation added. Soft plate checks are diagnostic only.

### Owner next

Hard-refresh new App SHA → ordinary top/shorts OpenAI Try On once (expect normal completed preview). Optionally re-check green jumpsuit OpenAI path (hints retained; no false person-mask failure). FASHN Accept on swimwear still requires explicit Accept.

## #170 P0 Garment identity fidelity + FASHN post-Accept failure — DEPLOYED (2026-11-02)

### Diagnosis (stored evidence only — **0** paid calls)

| Attempt | Realism job | Accept | FASHN job | Class | Credits |
|---|---|---|---|---|---|
| 1 | `95e8f3a7-…` (fp `08f488…`) | nginx **403** 12:59:33 UTC | **none** | **1 — local validation/enqueue (edge allowlist)** | **0 FASHN** · realism reservation **settled 8¢** (prior paid step) |
| 2 | `1011d39a-…` (fp `08f488…`) | nginx **403** 13:01:07 UTC | **none** | **1 — same** | **0 FASHN** · realism **settled 8¢** |

- `owner_accepted` stayed **false**; Accept never reached FastAPI; no `/v1/run`; no prediction IDs; nothing to recover from FASHN.
- Root cause: #169 shipped Accept route + FE, but nginx only allowlisted exact `POST .../garment-realism` (enqueue). Path `.../garment-realism/{uuid}/accept` fell through `location /api/v1/ai/ { return 403; }`. FE mapped bare 403 → “Something went wrong.”

### Trouser legs / green jumpsuit

| Stage | `08f488…` (failed FASHN review) | `ab5f725b…` / OpenAI `bf31ce76` |
|---|---|---|
| Studio UI | Long green legs visible | Long green legs |
| Captured garment / studio_context | **Bodice-only** (lower55%=0) | Full legs present |
| Prep plate | Bodysuit-like `one-pieces` | Legs retained through prep historically |
| Realism product | Swimsuit/bodysuit | n/a (OpenAI try-on) |
| OpenAI Try On result | n/a | Completed but **wide flares** (owner rejects) |

**Legs lost at/before garment capture input to prep** for `08f488` — not inside OpenAI realism. Prep then correctly classified the truncated plate as swimsuit-like `one-pieces`. OpenAI V2 flare on `bf31ce76` is model behavior given weak hints; garment PNG still had narrow legs.

### Fixes

1. Nginx regex allowlist `POST .../garment-realism/{uuid}/accept` + verifier/docs/tests.
2. Prep completeness + **jumpsuit/trousers fail-closed** (do not map to swimsuit `one-pieces`); bikini/two-piece preserved.
3. FE capture completeness vs live ink span; clearer Accept **403** message.
4. Additive OpenAI V2 trouser design hints (FE fills + BE garment geometry) — **prompt version stays `try-on-person-v2`**.
5. Soft post-generation structure review → `completed_unverified` when legs merged/flared; does not auto-refund.

### Owner next (single controlled test)

Hard-refresh new App SHA → same green jumpsuit → **Try On Person (OpenAI)** once. Expect trouser hints in job + no silent flare presented as faithful if soft review fails. For FASHN: jumpsuit should **block at prep** with an explicit message (use OpenAI path). Swimwear two-piece Accept should work after nginx fix.

### Deployed

| Field | Value |
|---|---|
| App / FE / BE / worker SHA | **`dcee9eac31ea6891177911896036542b321d4581`** (App **`dcee9eac`**) |
| Alembic | **`015`** (unchanged) |
| Nginx | Accept regex allowlisted (quoted) · health/ready **200** |
| Provider calls this window | **0** |
| Backup / rollback | `/var/backups/fashionrise/p0-170-jumpsuit-deploy-20261102T134040Z/ROLLBACK.sh` → FE **`6ef5c109`** |

### Rollback

`/var/backups/fashionrise/p0-170-jumpsuit-deploy-20261102T134040Z/ROLLBACK.sh` → FE **`6ef5c109`** + prior BE overlays + prior nginx.

## #169 Restore manual garment approval before FASHN — DEPLOYED (2026-11-02)

### Private diagnosis (stored artifacts only — **0** paid calls)

| Test | Jobs | Confirmed stage of redesign | Unknown |
|---|---|---|---|
| Brown/yellow-dot two-piece | try-on `eac2ad77…` · realism `d71f6619…` (v5) | **OpenAI realism** thickened bottoms vs Studio/prep plates (`FIDELITY_COVERAGE_EXPANDED` would now block). FASHN final further restyled (square neck / wider straps / thicker bottoms). | Exact strap geometry deltas in FASHN output not quantified beyond visual compare. |
| Deep-V narrow-strap one-piece | try-on `6c6bb772…` · realism `fe71c680…` (v5) | OpenAI product remained swimsuit-like. **FASHN** introduced midi skirt / extra fabric. | Which FASHN category/internal heuristic invented the skirt (category was already `one-pieces`, not `auto`). |

Prep plates matched Studio silhouette for both. FE-sent approved piece SHAs previously differed from product SHAs; server now binds FASHN garment bytes from the realism job after Accept.

### Behavior change

1. Magic → FASHN Try On → consent → prep → OpenAI realism → **owner review dialog** (sketch vs product; two-piece shows Top/Bottom).
2. Actions: **Accept & Try On**, **Regenerate Garment**, **Cancel** (no ¢ on buttons; costs in dialog body).
3. Only Accept stamps `owner_accepted` then enqueues FASHN. Cancel/close never starts FASHN.
4. Hard fidelity failures still show product when available; Accept stays disabled (server also rejects override).
5. Design/croquis edits invalidate pending approval. Regenerate uses a new idempotency key.
6. Ordinary OpenAI Try On V2 path unchanged and independent.

### Fidelity

- Added **`FIDELITY_COVERAGE_EXPANDED`** for skimpy triangle bottoms that grow absolute lower-band / opaque coverage (owner two-piece bottoms).
- Does **not** claim FASHN will preserve every detail after Accept — only that FASHN never runs on unapproved / fidelity-failed products.

### Tests / deploy

- BE `#169` + FASHN/try-on suite: **45 PASS** · FE review/dialog/layout + vite flags: **24+ PASS** · prod build gates **pass** · **0** operator-paid OpenAI/FASHN calls in implement/deploy window
- Accept route live: `POST /api/v1/ai/personal-try-on/fashn/garment-realism/{job_id}/accept`
- Rollback: `/var/backups/fashionrise/p1-169-manual-approve-deploy-20261102T124937Z/ROLLBACK.sh` → FE **`d6caad30`** + prior BE overlay files
- Deployed SHA: **`6ef5c109bd31634c2a76fb217d1636d4adf90141`** (App **`6ef5c109`**) · Alembic **`015`**

### Owner next

Hard-refresh App **`6ef5c109`** → Magics → **FASHN Try On**. After realism, compare sketch vs product. Reject/Regenerate if bottoms thicken or straps/neckline change. Accept only when product matches. Then judge FASHN final separately — Accept does not guarantee FASHN fidelity.

## #166/#168 P0 Restore regular OpenAI Try On (v2) — DEPLOYED (2026-11-02)

### Failed job (owner ~12:15 Asia/Jerusalem = 10:15 UTC)

| Field | Value |
|---|---|
| Job | `461c9419-ae6d-4ac3-a1c1-570a5adcff9a` · `personal_try_on` · **failed** |
| Provider | **`openai`** (not FASHN) · `prompt_version=try-on-person-v3` |
| HTTP | OpenAI **did** receive request · `400` · `code=moderation_blocked` |
| Rejection | `moderation_stage=input` · `categories=["sexual"]` · `request_id=req_707f74be1be74048897bdae9e15fc584` |
| Reservation | `0d53b2db-…` · **`released`** · `provider_called=true` · `actual_cost_cents=null` |
| Garment | Magenta V-neck top + coral/orange shorts + cap (ordinary opaque street clothes) |
| Photo | Same `source_asset_id=687d4307-…` as last successful ordinary Try On |

### Compare vs last successful ordinary OpenAI Try On

| | Success `12010ebc…` | Failure `461c9419…` |
|---|---|---|
| When | 2026-11-01 23:49 UTC | 2026-11-02 10:15 UTC |
| Provider / prompt | OpenAI · **`try-on-person-v2`** | OpenAI · **`try-on-person-v3`** |
| Photo | Same croquis source asset | Same |
| Outfit | Pink crop + dark shorts + cap | Magenta top + orange shorts + cap |
| Outcome | **completed** | **PROVIDER_MODERATION_BLOCKED** |

Fleet: **0/5** `try-on-person-v3` jobs succeeded — all `moderation_blocked` / `sexual` / `input`. V3 started failing at **00:14 UTC** (before App `e26b9a43` FASHN realism deploy at ~09:03 UTC).

### Did latest FASHN work cause this?

**No.** Routing stayed OpenAI (`provider=openai`). Failure mode is OpenAI input moderation under live prompt **v3** (#156 swimwear wording), not FASHN realism/prep. FASHN jobs in the same window completed normally.

### Fix

Restore live OpenAI Try On to **`try-on-person-v2`** (last known-good ordinary-outfit prompt). Keep V3 text archive-only. FASHN swimwear path / realism v5 / Magic / V5 croquis unchanged. No moderation bypass, no silent provider switch, no auto paid retry.

### Owner next

Hard-refresh App **`d6caad30`** → same magenta top / orange shorts / cap → Magic → **Try On Person** (OpenAI button, not FASHN). Expect a photoreal preview when the provider accepts. Swimwear remains on **FASHN Try On**.

### Tests / deploy

- BE personal try-on: **15 PASS** · FASHN realism suite: **17 PASS** · FE try-on/layout: **20 PASS** · **0** paid calls
- Rollback: `/var/backups/fashionrise/p1-168-try-on-restore-v2-deploy-20261102T112822Z/ROLLBACK.sh` → FE **`e26b9a43`** + prior BE `personal_try_on_provider.py`
- Deployed SHA: **`d6caad30f6ca72d67ecd40317c405785fbf06968`** (App **`d6caad30`**)

## #167 Reuse Fashion Magic design fidelity for FASHN realism — DEPLOYED (2026-11-02)

### Private diagnosis (failed realism `5842e98b…`, App `6c6140ef`, prompt v4)

| Check | Finding |
|---|---|
| Product PNG stored? | **No** — fidelity failed before save (`stored_files=[]`). Only width profiles + plates available. |
| Source tops plate | Separated purple cups, deep open V (`width_profile` tip **9** / mid **160** → tip ratio **0.056**) |
| OpenAI product profile | Tip **77** / mid **413** → tip ratio **≈0.186**, growth **≈3.31** |
| Gate that fired | Relative-only `top_growth >= 2.5` (absolute fill-in **0.70** did **not** fire) |
| Known #164 wrap (for scale) | Tip ratio **≈0.253**, growth **≈5.70** — clear redesign (asymmetric straps, lost gradient) |
| Verdict | **Borderline / likely false reject** of soft-edge photoreal tip thickening on separated-cup deep-V plates. Cannot visually confirm redesign without product bytes. Relative-only gate was too aggressive. |

### Fixes

1. **Realism prompt v5** — import Fashion Magic **`COVERAGE_PRESERVATION_CONTRACT`** + **`COLOR_FIDELITY_CONTRACT`** (swim openings, deep necklines, bikini cuts, midriff). Add authoritative geometry + product-only contracts. **Do not** copy FM illustration-style (non-photoreal) instruction.
2. **Studio croquis context** — downscaled full Studio capture attached as images.edit Image 2; plate (Image 1) remains silhouette/fill authority. Offline `local_design_identity_bits` mirrors FM structured coverage fields (no paid vision call).
3. **Neckline gate calibration** — reject only absolute V fill-in (`tip ≥ 0.70`) or wrap-class thickening (`tip ≥ 0.22` **and** growth `≥ 4.5`). Soft 2–3× tip growth on deep-V plates can pass; #164 wrap still fails.
4. **Persist failed products** — fidelity failures still save product PNG + `failed_product` URL for private diagnosis; FASHN remains blocked.
5. **Spinner costs** — remove ¢ from realism/FASHN progress hints; keep ¢ disclosure in the confirmation dialog before paid actions.

### Owner paid-test budget

Still max **2–3** owner-paid FASHN swimwear tests. If still not clearly good after this correction, discontinue personal swimwear try-on.

### Owner next

Hard-refresh App **`e26b9a43`** → purple bikini → Magic → **FASHN Try On**. Expect spinner “Generating realistic garment…” (no ¢) then FASHN credits hint without ¢. Confirmation dialog still shows stage costs. Final look must keep deep-V / separated cups / gradient while looking like photoreal fabric.

### Tests / deploy

- BE bikini/prep/realism/fidelity: **26 PASS** · FE layout CTA + try-on API: **13 PASS** · **0** paid calls in deploy window
- Rollback: `/var/backups/fashionrise/p1-167-fm-realism-fidelity-deploy-20261102T090347Z/ROLLBACK.sh` → FE **`6c6140ef`** + prior BE overlay
- Deployed SHA: **`e26b9a43dc16100f99e17c3e19b988ab4f2a870d`** (App **`e26b9a43`**)

## #166 FASHN requires OpenAI realism (no sketch-plate input) — DEPLOYED (2026-11-02)

### Root cause (owner App `c2d0ba41`, realism `9b837e89` → try-on `6f4c8c36`)

| Check | Finding |
|---|---|
| Realism stage ran? | Job completed, but provider was **`local_filled_plate_v1`** (`prefer_local_product=true`, **$0**) — **OpenAI images.edit did not run** |
| Realistic asset produced? | No — RGB re-encode of Studio plates (identical pixels/silhouette; hard outlines retained) |
| What FASHN received? | Approved piece SHAs **`e7da6229…` / `2d9e28d8…` = exact prep plates**, not OpenAI products. Linked via `garment_realism_job_id=9b837e89…` |
| Tops/bottoms | Two sequential FASHN credits; both used sketch-like plates |

**Why worse than prior:** #164 skipped OpenAI to protect cut/gradient, but FASHN then tried to dress the person from illustrated plates → flat/outlined garment look.

### Fixes

1. **Disable local plate skip** — `prefer_local_product` always false; realism always paid OpenAI **v4** (fabric, no sketch strokes).
2. **Server-bound FASHN inputs** — require `garment_realism_job_id`; load pieces from that job; reject non-`openai_garment_realism` / local / plate-SHA passthrough.
3. **CTA/costs** — button stays `FASHN Try On`; confirmation lists OpenAI + FASHN stages separately.

### Owner paid-test budget

Max **2–3** more owner-paid FASHN swimwear tests from this point. If still not clearly good, stop personal swimwear try-on and keep OpenAI croquis/mannequin only.

### Owner next

Hard-refresh App **`6c6140ef`** → purple bikini → Magic → **FASHN Try On** once. Expect status “Generating realistic garment (~N¢ OpenAI)…” then FASHN. Final look must be photoreal fabric (not sketch outlines) while keeping cut/coverage/gradient.

## #164 P1 FASHN bikini design fidelity + clean CTA — DEPLOYED (2026-11-02)

### Root cause (owner paid test App `a3ca2221`, realism `510101dc…` → try-on `fd053d92…`)

| Stage | Result |
|---|---|
| Studio sketch (purple two-piece bikini) | Deep-V top, intended bottoms coverage, purple gradient |
| Transparent capture + prep plates | **Faithful** (fill ≈ 0.885 / 0.845); two-piece tops→bottoms |
| OpenAI garment realism v2 | **Drift origin** — restyled deep-V into twisted/wrapped top; bottoms waist/coverage + gradient placement shifted |
| FASHN v1.6 | Applied the **already-restyled** product plates faithfully onto the person |

**Drift stage:** OpenAI realistic garment generation — not FASHN, not prep.

### Fixes shipped (App `c2d0ba41`)

1. **Local productize for dense filled plates** (`prefer_local_product`): skip OpenAI redesign; keep exact Studio cut/colors/gradient; realism estimate **$0**.
2. **Realism prompt v3** when OpenAI still needed: forbid invented twists/wraps; preserve neckline, waistline, coverage, gradient; inject dominant color hints.
3. **Fidelity:** `FIDELITY_NECKLINE_CHANGED` (+ asymmetry/color) blocks FASHN when OpenAI fills in a deep-V / invents redesign.
4. **CTA:** button label exactly **`FASHN Try On`**; combined OpenAI+FASHN estimate stays in confirmation copy only.

### Tests / deploy

- BE bikini/prep/realism/fidelity/try-on: **35 PASS** · FE layout CTA + try-on API: **15 PASS** · prod vite flags + notices **pass** · **0** paid calls in deploy window
- Rollback: `/var/backups/fashionrise/p1-164-bikini-fidelity-deploy-20261102T070311Z/ROLLBACK.sh` → FE **`a3ca2221`** + prior BE overlay

### Owner next

Hard-refresh until App **`c2d0ba41`**. Open the purple two-piece bikini sketch → Magic → confirm button reads **FASHN Try On** (no ~¢ on the button; cost still in the dialog text) → run once. Expect progress “Keeping exact Studio cut and colors…” then FASHN. Final person photo should keep deep-V top, bottoms coverage, and purple gradient — still photorealistic, not a sketch.

## P1 FASHN fidelity + one-click UX + mobile CTA — DEPLOYED (2026-11-02)

### Root cause (owner paid test jobs `fb55f220` → `0df11dea`)

| Stage | Artifact | Silhouette |
|---|---|---|
| Source sketch | immutable Studio capture | High-cut asymmetric one-piece swimsuit, blue→magenta gradient |
| Garment prep plate | offline flat-lay | **Preserved** swimsuit (category was wrongly `auto`) |
| OpenAI realism `fashn-garment-realism-v1` | product PNG | **Preserved** swimsuit |
| FASHN v1.6 with `category=auto` | final person image | **Changed** into asymmetric mini-dress / skirt hem |

**Actual transformation responsible:** FASHN Virtual Try-On with `category=auto`, not the realism stage. Realism was structurally faithful; FASHN reinterpreted high-cut leg openings as a handkerchief skirt.

### Fixes shipped (App `a3ca2221`)

1. **Category:** one-piece swimwear → FASHN `one-pieces` (never `auto`).
2. **Realism prompt v2:** explicit ban on dress/skirt conversion; preserve high-cut openings.
3. **Structural fidelity gate** before FASHN credits — fail closed on swimsuit→dress (does **not** claim perfect image fidelity; only silhouette class checks).
4. **One-click UX:** Magic → FASHN Try On (~combined ¢) runs prep → realism → fidelity → FASHN with progress hints; intermediate Accept dialogs removed from normal path.
5. **Mobile CTA:** ConfirmDialog uses `dvh` + `visualViewport` chrome inset so the pink primary stays tappable above browser toolbars.

### Costs shown

- Combined one-piece estimate ≈ **16¢** (realism 8¢ + FASHN 8¢); two-piece doubles both stages.
- No automatic paid regenerations / retries.

### Tests / deploy

- BE fidelity/prep/realism/try-on: **27 PASS** · FE dialog/layout/API: **18 PASS** · **0** paid calls in deploy window
- Rollback: `/var/backups/fashionrise/p1-fashn-fidelity-oneclick-deploy-20261102T054908Z/ROLLBACK.sh` → `7015ca3f`

### Remaining limitations

- Fidelity gate is geometric (not a generative guarantee). A technically valid image can still look imperfect while passing silhouette class checks.
- FASHN may still reinterpret unusual silhouettes; owner visual review in My Looks remains required.
- OpenAI Try On Person path unchanged.

### Owner next

Hard-refresh App **`a3ca2221`** → personal croquis → draw high-cut one-piece → Magic → **FASHN Try On (~16¢)** once → expect progress through realism/fidelity/FASHN → My Looks swimsuit (not a dress). Verify pink CTA fully tappable on Samsung Internet / Android Chrome.

## #161 P0 FASHN mobile review + realistic garment before try-on — DEPLOYED (2026-11-02)

Ships on top of #156/#158/#159 without overwriting V5 croquis, Fashion Magic, OpenAI Try On, or FASHN live-arm.

| Problem | Fix |
|---|---|
| Mobile garment-review dialog scrolled past Cancel / Confirm | `ConfirmDialog` viewport-bounded (`dvh` + safe-area), scrollable body, sticky footer; top/bottom previews with enlarge |
| Flat-lay sketch plates (often outline-only) went straight to FASHN | Prep fill retention + quality gate; paid OpenAI **`fashn-garment-realism-v1`** product image; owner Accept / Regenerate / Cancel; FASHN enqueue requires `approved_garment_pieces` |

| Item | Detail |
|---|---|
| App SHA | **`7015ca3f`** (`7015ca3f51676afb42f666bb6af2a49828b94702`) |
| Pipeline | Sketch → offline prep (free) → **Generate realistic garment** (OpenAI images.edit, paid) → owner review → **Accept & Run FASHN** (v1.6, paid) → My Looks |
| Costs shown | Realism **8¢ × pieces** · FASHN **8¢ × credits** · combined estimate before each paid step · no auto-retry / no silent accept |
| Nginx | Exact allowlist `POST /api/v1/ai/personal-try-on/fashn/garment-realism` |
| Tests | BE prep/realism/try-on/nginx **23 PASS** · FE ConfirmDialog viewport + try-on API + layout **14 PASS** · prod `ASSERT_PROD_CROQUIS_NOTICES=pass` · live OpenAPI route + **0** paid jobs in deploy window |
| Backup / rollback | `/var/backups/fashionrise/p0-161-garment-realism-deploy-20261102T014302Z/ROLLBACK.sh` → prior FE **`f102cbc4`** + prior BE/nginx |
| Preserved | V5 croquis · original photo binding · Magic · OpenAI Try On · FASHN key/`LIVE_HTTP` · single-checkbox consent · My Croquis / Designs / Looks · privacy/spend caps |

### Owner verification (first paid test is owner-initiated)
1. Hard-refresh App **`7015ca3f`** on phone (320–393 wide): Magic → **FASHN Try On** → footer Cancel / Generate always reachable; scroll sketches + enlarge top/bottom.
2. Draw filled opaque swimsuit (not outline-only). Prep must pass quality; then **Generate realistic garment** (~8¢/piece). Compare Step 1 sketch vs Step 2 product image; Regenerate or Cancel without FASHN spend.
3. Only after **Accept & Run FASHN** (~8¢/credit; two-piece = 2) expect photorealistic person wearing the approved garment in My Looks.

## #158+#159 P0 Create My Croquis notices + personal Fashion Magic — DEPLOYED (2026-11-02)

Owner found two production regressions while #156 FASHN swimwear work continued. Both fixed in one release on the FASHN branch (no overwrite of FASHN / V5 croquis prompt).

| Bug | Root cause | Fix |
|---|---|---|
| **#158** Create My Croquis blocked (“consent notices must be configured”) | `personalCroquisNotices.ts` used dynamic `import.meta.env[name]` — Vite production does not replace dynamic keys, so all three notices shipped empty | Static `import.meta.env.VITE_MY_CROQUIS_{ADULTS,STORAGE,AI}_NOTICE_TEXT`; prod build asserts non-empty + SHA256 match backend + embed in bundle (`COMPILED_NOTICES.json`) |
| **#159** Fashion Magic on personal croquis → `reference_model_id is not a recognized Studio model` | `doc.model=personal` sent as `reference_model_id`, but BE allowlist only had builtins/legacy/custom/blank | `PERSONAL_IDS={"personal"}` with `kind=personal`, `family=None`; vision/edit instructions preserve personal figure (no map to `female-straight`); single + dual enqueue paths covered |

| Item | Detail |
|---|---|
| App SHA | **`f102cbc4`** (`f102cbc46eee40598c26b7ccd1fea419f81723e4`) |
| Notice versions | `adults-beta-2026-11-01` · `storage-2026-11-01` · `ai-provider-2026-11-01` |
| Notice SHA256 (FE=BE) | adults `882c9ed4…` · storage `27882295…` · AI `c3226ed3…` |
| Tests | BE `test_reference_croquis_identity` **50 PASS** · FE notices+assert **22 PASS** · CreateMyCroquisWizard **4 PASS** · prod build `ASSERT_PROD_CROQUIS_NOTICES=pass` · **0** paid OpenAI/FASHN |
| Backup / rollback | `/var/backups/fashionrise/p0-158-159-deploy-20261102T012218Z/ROLLBACK.sh` → prior FE **`9aeea3f3`** + prior BE files |
| Preserved | FASHN live-arm (`key_present` / `FASHN_TRY_ON_LIVE_HTTP=true`) · croquis **v5** · Studio saves · My Croquis · My Looks · Try On Person · consent/finance controls |

### Owner verification (no agent-paid calls)
1. **Test A (#158):** Hard-refresh App **`f102cbc4`** → My Croquis → **Create New Croquis** → expect one-checkbox photo upload (not the “not ready yet” blocker). Do not need to upload.
2. **Test B (#159):** Open a saved personal croquis with a garment sketch → Magic → **Fashion Magic** → request must pass model validation (no `reference_model_id` error) and reach normal image-generation. Owner runs the paid polish after deploy.
3. Optional: still hard-refresh and run the first paid **FASHN Try On** swimwear test for #156 when ready.

## #156 P0 FASHN Try On v1.6 — LIVE-ARMED (awaiting owner first paid test) (2026-11-02)

OpenAI prompt tweaks stopped. Ordinary two-piece swimwear still fails OpenAI input moderation under V3. **FASHN Virtual Try-On v1.6** is now an explicit second Try On Person option.

| Item | Detail |
|---|---|
| Provider | `POST https://api.fashn.ai/v1/run` · `model_name=tryon-v1.6` · `moderation_level=permissive` · `num_samples=1` · `return_base64=true` · status poll · **no auto-retry** |
| Garment prep | Offline `fashn_garment_prep` → white flat-lay plate(s) from transparent Studio sketch (colors/shape preserved). Two-piece → **2 sequential credits** (tops then bottoms) — not a guess that one `auto` call applies both. |
| UX | Magic → **FASHN Try On** (when configured) → review prepared plate + cost → confirm → job. OpenAI **Try On Person** unchanged. Never auto-switch after refusal. |
| Consent | Separate `try-on-fashn-preview-v1` notice (FASHN-specific). |
| Spend | Shared croquis ceilings · idempotency `try_on:fashn:…` · reservation estimate = credits × `FASHN_TRY_ON_ESTIMATE_CENTS` (default 8¢) |
| Env | `FASHN_API_KEY` (secret) · `FASHN_TRY_ON_ENABLED` · `FASHN_TRY_ON_LIVE_HTTP` · estimate/base URL/poll timeouts |
| Tests | BE prep + try-on + nginx **17** PASS · FE API/layout **30** PASS · **0** paid calls |
| Deploy | App **`9aeea3f3`** · backup `/var/backups/fashionrise/try-on-fashn-20261102T010309Z` · nginx prepare allowlist live · `FASHN_TRY_ON_ENABLED=true` · `FASHN_TRY_ON_LIVE_HTTP=true` |
| Provider readiness | `key_present=true` · `fashn_configured=true` · `live_armed=true` · OpenAI try-on still live · **0** agent-paid FASHN calls |
| Owner first test | Hard-refresh App **`7015ca3f`** → personal croquis → draw opaque two-piece swimsuit → Magic → **FASHN Try On** → offline prep → **Generate realistic garment** (~16¢ for 2 pieces) → accept → FASHN (~16¢ / 2 credits) → My Looks. |

### Owner next (product acceptance)
1. Credits confirmed by owner.
2. Run the first paid FASHN swimwear test **in-app** after reviewing the plate cost (agent will not initiate paid calls).
3. #156 stays OPEN until that visual result is accepted.

## #156 P0 ordinary swimwear — provider suitability (2026-11-02) — OPEN (FASHN path shipping)

OpenAI prompt tweaks **stopped**. V3 is live and still unsuitable for ordinary two-piece swimwear. Specialist path: **FASHN AI** (see section above).

### 1) Latest production failure (safe diagnostics only)

| Field | Job ≈00:15 UTC | Follow-up ≈00:24 UTC |
|---|---|---|
| Job id | `d3e83594-57c3-4ea4-b3a3-fca2aa075e36` | `8ba362df-716c-458f-969c-5859772da3e2` |
| Created (UTC) | **2026-11-02 00:14:55Z** | 2026-11-02 00:24:16Z |
| Created (Asia/Jerusalem) | **2026-11-02 02:14:55** | 2026-11-02 02:24:16 |
| Prompt | `try-on-person-v3` | `try-on-person-v3` |
| Consent | `try-on-person-preview-v1` | same |
| Error | `PROVIDER_MODERATION_BLOCKED` | same |
| Provider rejection | `moderation_blocked` · HTTP **400** · stage **`input`** · categories **`["sexual"]`** · `req_d5eecc5453ad4ad2b05e744f760f954b` | same shape · `req_096d9dbafa5e4c0da8aef7342c893536` |
| Reservation | **released** · `actual_cost_cents` **null** · `provider_called` **true** · estimate 40¢ | same |
| App | **`e728a06c`** | same |

No new paid OpenAI retries by the agent. UI still shows the sanitized owner message; diagnostics stay in private `result_data.provider_rejection`.

### 2) FASHN AI evaluation (docs only — no network/paid FASHN calls)

| Topic | Finding |
|---|---|
| Best first endpoint for swimwear policy | **`tryon-v1.6`** — documents `moderation_level=permissive` (default) allowing swimwear/underwear while still blocking explicit nudity. `conservative` explicitly blocks swimwear. |
| Higher-fidelity candidate | **`tryon-max`** — better quality (up to 4K, prompt styling) but **no** documented moderation_level / swimwear policy control. Use after garment prep is proven, not as the first swimwear policy fix. |
| Model / person photo | Authorized original adult croquis photo maps cleanly to `model_image` (URL or data URI). Prefer **base64 + `return_base64: true`** so private photos are not left as long-lived CDN URLs. |
| FashionRise garment capture | Current capture is a **transparent Studio garment-only sketch PNG** (not a product / flat-lay / ghost-mannequin photo). FASHN examples and guides assume **product photographs**. **Do not assume the existing capture can be sent raw.** A legitimate product-image preparation step is required (e.g. composite two-piece onto a flat / ghost-mannequin style plate; two-piece may need one composite `one-pieces`-style plate or separate top/bottom runs). |
| Pricing (API on-demand) | **$0.075 / credit** · minimum purchase **100 credits ($7.50)**. v1.6 = **1 credit / output image**. Max = **1–5 credits** by `generation_mode` × `resolution` (× `num_images`). |
| Commercial rights | API plans include a **commercial use license** for generated images in products/PDPs/marketing per FASHN terms; uploader must hold rights / model consent (FashionRise already gates Try On with `try-on-person-preview-v1`). |
| Private-photo / retention | No training/fine-tune on Customer Content without separate opt-in. Base64 inputs deleted after processing (1-day backstop). Default CDN outputs ~3 days; `return_base64: true` → ~60 minutes. Request history retains parameters/URLs (base64 shown as placeholders). |
| Consent / ethics | FASHN ToS forbids misuse without consent of identifiable individuals; FashionRise must keep explicit user-triggered generation + existing adults/storage/AI consent — do **not** set `moderation_level=none` for this product. |

### 3) Preserve working FashionRise features

- Keep OpenAI Try On Person for clothing designs that already work.
- Add a **separate** FASHN adapter only for categories OpenAI rejects (or explicit routing), not a wholesale provider swap.
- Preserve V5 croquis, garment fidelity, My Looks, My Croquis, Fashion Magic, private photo binding, spend caps, safe failure UX, explicit user trigger.
- Do **not** disable moderation, auto-retry provider refusals, or introduce uncontrolled charges.

### 4) EXACT BLOCKER — owner configuration required

Prod `.env` and agent secrets have **no** `FASHN_*` credentials (OpenAI-only try-on stack). Integration and live swimwear validation **cannot** proceed without:

1. Create a FASHN account at [app.fashn.ai](https://app.fashn.ai).
2. Buy **API** credits under Billing → **FASHN API** (on-demand min **$7.50 / 100 credits**, or a commitment tier).
3. Create an API key at [app.fashn.ai/api](https://app.fashn.ai/api) (shown once).
4. Provide the key for server-side deploy only as e.g. `FASHN_API_KEY` (never client-side / never commit).
5. Explicitly authorize the first paid FASHN swimwear validation on the authorized original photograph + prepared garment plate.

Until those exist, **no adapter deploy and no mocked “success.”** #156 stays **OPEN**. Success = realistic Try On Person of an ordinary two-piece swimsuit on the authorized photo.

## CONFIG — daily AI generation quota disabled (2026-11-02)

Owner: **“Do not limit my ai tests.”** Prod was blocking after five Create My Croquis / Try On Person attempts with “Daily … generation limit reached.” That is an application count gate, not OpenAI moderation.

| Item | Detail |
|---|---|
| Change | Persistent `MY_CROQUIS_AI_MAX_GENERATIONS_PER_USER_DAY=0` in `/opt/fashionrise/src/backend/.env` |
| Effect | Count gate in `personal_croquis_generate` + `personal_try_on` is **skipped** when `max_gens > 0` is false — both flows |
| Restart | `fashionrise-api` + `fashionrise-ai-worker` · health/ready **ok** |
| Effective | `get_settings().my_croquis_ai_max_generations_per_user_day == 0` |
| Unchanged | App **`e728a06c`** · try-on **v3** · moderation handling · no auto-retry · Alembic **015** · historical reservations untouched |
| Money caps still on | Ceiling **`$5.00`** · per-user-day **`$5.00`** · per-run **`$1.00`** · max exposure **100¢** |
| Current spend (snapshot) | Settled actual **21¢** all-time / 24h · open/recon **0** · billable reservations last 24h **5** (count no longer blocks) · released 24h **5** |
| Backup / rollback | `/var/backups/fashionrise/ai-gen-quota-disable-20261102T001027Z/ROLLBACK.sh` |
| Owner next | Resume AI tests immediately; if a **money** cap blocks later, raise the cash budget intentionally — do not treat count as infinite spend. |

## #156 Try On Person swimwear moderation + clean mobile errors — DEPLOYED (2026-11-02)

Owner swimsuit Try On failed with provider **HTTP 400** `moderation_blocked` / `input` / `sexual`. Offline job `be37d55e…` (≈01:40 Israel): photo = authorized `croquis_source`; garment = transparent RGBA 1536×2048 (~98% alpha, no mannequin/paper); effective prompt was **V2** with contradictory “do not expose body beyond image 1”; spend reservation **released** at $0. Capture was not the corruption source; prompt contradiction was a concrete product defect. Which input bit the classifier is still not proven.

| Item | Detail |
|---|---|
| Prompt | **`try-on-person-v3`**: opaque fashion/swimwear lookbook; designed coverage authoritative; still forbids nudity / sheer intimate exposure / sexual framing; keeps V2 print/accessory fidelity |
| Errors | Owner UI: short “could not be rendered… continue editing or Fashion Magic”. Diagnostics (`code`/`stage`/`request_id`) stay in private `result_data.provider_rejection`. Mobile error text wraps/scrolls. |
| Spend | Definite HTTP 400 → reservation **released**, `actual_cost_cents` null, **no** automatic paid retry |
| Unchanged | V5 croquis · Fashion Magic · consent · My Croquis · #148 A→B · #154 compare/fidelity capture |
| Tests | BE try-on **12** PASS · FE error sanitize / capture / MagicLookPanel PASS · **0** paid calls |
| Deploy | FE+BE+worker **`e728a06c`** · backup `/var/backups/fashionrise/try-on-swimwear-20261101T235431Z` |
| Owner verify | Hard-refresh App **`e728a06c`**. Optional owner-paid swimwear Try On. Expect no self-contradictory coverage instruction; on any future provider refusal, a short readable message (no raw JSON). Acceptance of a realistic swimsuit result still depends on the image provider. |

## #154 Try On Person V2 — DEPLOYED (awaiting owner live review) (2026-11-02)

Owner accepted V1 realism. Next ask: preserve patterns/colors/shapes/accessories (pink checkers→stripes / missing cap), better original-vs-generated compare + private Save/Download via My Looks, and small My Croquis polish — without changing V5 croquis, Fashion Magic, photo binding, one-checkbox consent, or spend caps.

| Item | Detail |
|---|---|
| Diagnosis | Garment capture already includes strokes/fills; fidelity loss was primarily **provider prompt** (print topology / accessories under-emphasized). Capture also bumped to **2×** (1536×2048) so fine prints survive resize. |
| BE | Prompt **`try-on-person-v2`** (checker≠stripes; include hats/caps). Optional bounded `design_hints` frozen on the job. Consent still `try-on-person-preview-v1`. Photo still bound server-side to accepted croquis `source_asset_id`. |
| FE preview | Try-on panel: result → side-by-side original vs try-on → original → garment. **Download preview** + **Save in My Looks** reuse existing private looks path. |
| My Croquis | Retry Delete works after API error; Create New returns to gallery for preview/selection (no auto Studio jump). #148/#151 A→B pin save unchanged. |
| Unchanged | V5 croquis generator · Fashion Magic polish · owner-photo binding · one-checkbox consent · spend ceiling |
| Tests | BE `test_personal_try_on` **12** PASS (mocked) · FE MagicLookPanel/MyCroquis/hints/API **13** PASS · **0** paid `images.edit` |
| Deploy | FE+BE+worker **`fe1e9e8b`** · Alembic **015** · backup `/var/backups/fashionrise/try-on-v2-20261101T233405Z` |
| Owner verify | Hard-refresh until App **`fe1e9e8b`**. Personal croquis → redraw pink checkers + shorts + cap → Magic → **Try On Person** (owner-paid). Expect checkers (not stripes), cap present, colors preserved. Use **Compare original** / side-by-side, Download, Save in My Looks. My Croquis: Create New stays in gallery; Retry Delete after a forced error. Do **not** clear IndexedDB. |

## #148 + #151 Personal croquis A→B fix + My Croquis library — DEPLOYED (2026-11-02)

Owner reopen of #148: built-in↔personal fixed on App `6668e382`, but **personal A → personal B** still false-conflicted. #151 asks for a first-class **My Croquis** gallery beside My Designs / My Looks.

| Item | Detail |
|---|---|
| Root cause (#148 reopen) | BE `_studio_content_fingerprint` **omitted** `personalCroquisId` / `personalCroquisVersion`. Pin-only A→B (same strokes/model) looked like identical content → PUT **200** returned the **prior** pin → FE `acknowledgedFingerprint !== cloudFingerprint` → false Draft recovery. Distinct from the non-personal stray-pin bug. |
| Fix | BE fingerprint + normalize pins (personal only). FE `applyPersonalCroquisPin` is one atomic commit (`skipNextAutosaveRef`) + Keep/Clear when ink; wizard/gallery use `requestPersonalCroquisPin`. |
| My Croquis (#151) | Nav + `/studio/croquis` gallery: authenticated thumbnail preview, Use in Studio (exact accepted version), Delete with Studio-ref warning + private erase, Create New via existing one-checkbox wizard. No public photo URLs. |
| Try On (#149) | Unchanged — still binds server-side `source_asset_id` to the active selected personal croquis + garment-only snapshot. |
| Tests | FE: personal pin A→B fingerprint/persist, MyCroquisScreen, StudioPage notices — focused PASS. BE: fingerprint unit + concurrency pin-switch coverage. **0** paid OpenAI. |
| Deploy | FE **`85a50894`** · BE `design_service.py` pin fingerprint · backup `/var/backups/fashionrise/my-croquis-switch-20261101T224921Z` · Alembic untouched |
| Owner verify | Hard-refresh until App **`85a50894`**. Open **My Croquis** → preview A and B → **Use in Studio** on B → wait **Saved** → refresh still B → select A → **Saved** (no false conflict), with/without strokes (Keep/Clear). Create New + Delete from gallery; if Studio pins the deleted croquis, strokes remain / underlay unavailable. Try On Person still uses the active croquis photo. Do **not** clear IndexedDB. |

## #149 Try On Person — DEPLOYED (awaiting owner live review) (2026-11-01)

Owner-accepted Create My Croquis V5. Next product ask: sketch on personal croquis → Magic → choose **Fashion Magic** (unchanged illustration polish) or **Try On Person** (photorealistic garment on the original photo).

| Item | Detail |
|---|---|
| UX | Personal croquis + Magic → destination dialog. Built-ins keep existing Magic only. User can return to sketch and choose either path independently. |
| Capture | Transparent **garment-only** PNG (`garmentOnly`) — strokes/fills/fabrics, no paper/mannequin; frozen with `clientRevision` + fingerprint at enqueue. Mid-flight mannequin switch refuses try-on start. |
| BE | Job type `personal_try_on`; prompt `try-on-person-v1` (photo = identity/pose/background; garment = design). Server resolves `source_asset_id` from owned accepted croquis. Consent `try-on-person-preview-v1`. Spend via `PersonalCroquisSpendReservation` (`try_on:` idempotency). Private look image + My Looks + delete. |
| Unchanged | V5 croquis generator · Fashion Magic polish prompt · #148 draft pin hotfix |
| Tests | BE `test_personal_try_on` + nginx allowlist **11** PASS · FE garment capture / MagicLookPanel try-on / API client / Studio Magic regressions PASS · **0** paid `images.edit` by agent |
| Deploy | FE+BE+worker **`0676a9a6`** · Alembic **015** · nginx try-on allowlist · backup `/var/backups/fashionrise/try-on-person-20261101T182849Z` |
| Owner verify | Hard-refresh until App **`0676a9a6`**. Open accepted personal croquis → draw garment → Magic → **Try On Person** (owner triggers first paid call). Expect photorealistic preview of original person in the design; sketch + original photo unchanged. Fashion Magic still available. Built-in mannequin Magic unchanged. Do **not** treat deploy as successful realistic try-on until owner reviews a real result. |

## #148 Studio draft conflict / Keep-this-device Save failed (2026-11-01) — DEPLOYED

Owner: switch mannequin → **Draft recovery conflict** → **Keep this device** → **Save failed Retry**; **Use cloud draft** showed the new mannequin + Saved. Prod API window had **PUT 200s / 0× HTTP 409**.

| Item | Detail |
|---|---|
| Root cause | Stray `personalCroquisId` / `personalCroquisVersion` on **non-personal** models survived cloud writes and fingerprints, while `parseStudioDraftDocument` strips them on read → fingerprint mismatch after **PUT 200** opened a **false** Draft recovery conflict. No-ink `requestModelChange` only called `setModelState`, so leaving personal / carrying pins never cleared. Keep-this-device rebased the stale conflict snapshot and hit the same mismatch → Save failed. Use-cloud only replaced IndexedDB with the parsed server doc (pins already null, new model) → Saved. |
| Fix (FE-only) | Normalize/strip non-personal pins in fingerprints, serialize, editor commits, and rebase; no-ink model switch goes through `commitModelChange`; Keep uses **live canvas** + **one OCC rebase retry** (second concurrent race renews conflict); Use-cloud unchanged; local recovery never auto-erased. |
| Tests | Vitest: `personalCroquisPins`, `draftPersistence` (#148 model-switch), `conflictResolution` (Keep rebase + dual-race), undo/queue Studio — **95** focused PASS; broader Studio designs/frontBack/restore **53** PASS. |
| Deploy | FE release **`6668e382`**; backup `/var/backups/fashionrise/studio-draft-conflict-hotfix-20261101T180530Z`; BE/worker/Alembic untouched; **0** paid AI. |
| Owner verify | Hard-refresh until App **`6668e382`**. Single tab: switch Female Standing → Hand on hip (no ink) → expect **Saved** (no conflict). With ink: confirm keep/clear strokes still works. Optional: open conflict via two tabs; **Keep this device** should preserve model/strokes/Front-Back; **Use cloud** still available. Refresh must keep chosen model. Do **not** clear IndexedDB. |

## #135 Create My Croquis — V5 photo-faithful proportions (2026-11-01)

Owner V4 acceptance: house mannequin **style PASS**, pose mostly preserved, but figure was too tall/slim vs photographed person. V5 makes **image 1 (photo) authoritative for geometry** and **image 2 (house croquis) style-only**.

| Change | Detail |
|---|---|
| Prompt | **`croquis-lineart-v5`** — preserve relative widths, head-to-body, torso-to-leg; forbid auto-slim / leg lengthening; do not copy image 2 body shape |
| Removed | V4 “elongated fashion-figure silhouette” wording |
| Mode | `proportion_mode=photo_faithful` (default; not fashion_elongated) |
| Unchanged | consent · moderation=low via extra_body · spend bounds · private storage · transparent underlay · accept/delete |
| Tests | BE focused **42** · **0** paid `images.edit` |
| Owner eval | Hard-refresh App **`faa7d91d`** → Upload & Generate → compare proportions visually (not cm claims) |

## Try On Person — owner workflow (now live on App `e728a06c`, prompt v3)

1. Generate / accept a photo-faithful mannequin (Create My Croquis V5).
2. Draw a clothing design in Studio on that underlay.
3. Click **Magic** → **Try On Person** (or **Fashion Magic** for the illustration path).
4. FashionRise uses the privately stored **original photo** + **isolated garment artwork layer** to create a private photorealistic preview.
5. Review, download / My Looks, or delete — original photo and drawing are not overwritten.

Concept preview only — **not** a fit or measurement guarantee.

## Issue #128 / PR #130 — Magic source provenance closure — STOP for Technical PM final acceptance (2026-10-29)

Technical PM **PARTIAL PASS** on tip `983372f7` / implementation `4cb7d8f0` / blob `2b684a28` — structural + visual identity accepted; one narrow P0 remained: skip-path artifacts still attributed live `draft.front_job_id`/`look_id` when Magic source changed mid-run. This tip captures immutable generation-boundary Magic source IDs and uses them for paid-artifact provenance on **both** Professional completion paths (bind + identity-drift skip).

| Item | Detail |
|---|---|
| Tip / GitHub HEAD | `c16acf41013a39eb83b68ef40105fe3498f6cd06` |
| Implementation commit | `0561bb56cf49d69b9c2349a94dd54b79585a1f5f` |
| Implementation blob | `e04fdbcf6f5fba8dc868094c86874e365cebc321` (`techpack_ai.py`) |
| Prior accepted | `4cb7d8f0` / `2b684a28` structural+visual · `0e341c10` identity+PDF CAS · POM overlay |
| Branch | `cursor/web-techpack-meas-preserve-77c6` (descendant of prod BE **`311e259a`**) |
| PR | [#130](https://github.com/perielad2-netizen/FashionRise/pull/130) vs `cursor/web-techpack-be-prod-311e259a-77c6` @ `311e259a` |
| Production (unchanged) | FE **`bfbdd03f-decimal`** · BE+worker **`311e259a`** · Alembic **`011`** |
| P0 Magic provenance | `capture_generation_boundary` stores `look_id`/`front_job_id`/`back_job_id`. `_persist_professional_result(..., generation_boundary=)` sets artifact `source_job_id`/`look_id` from that snapshot (front\|\|back semantics unchanged). Live draft source IDs never rewrite historical paid rows. |
| Regressions (mocked) | Magic look/front swapped mid-run (independent session): private bytes retained; artifacts keep **original** source IDs; draft keeps **newer** source; artwork unbound; no PDF bind; cost retained; **exactly one** provider call. Happy path: provenance matches unchanged draft sources. |
| Preserved | Finished POM · concurrent measurement CAS · PDF CAS · structural artifact retention · gradient/visible-detail identity · cost without paid retry |
| Tests | Focused integrity+concurrent **18/18**. Broader Professional/PDF/p0/v3/async: **81 passed**, **1** baseline `test_partial_cost_preserved_on_failure` (`KeyError: 'status'`) on `311e259a`. |
| Lint | Ruff `techpack_ai.py` **9** (baseline parity). mypy **51** (parity). |
| Safety | **No deploy · no migration · no paid AI · no data restore · #125 / #129 independent** |
| Exact next action | **STOP** for Technical PM final acceptance of PR #130. **Do not deploy.** |


### Prior enrich fix (still in tip — PM accepted)

| Item | Detail |
|---|---|
| Code | `6ac13dc34903e03aa992769fb48721647abd4620` |
| Root cause | `_propose_finished_measurements` rebuilt from `empty_finished_measurements()` and only copied prior cells inside `set_calc` keys → shorts outseam/thigh/waistband dropped |
| Fix | Overlay entire existing `finished_measurements`; propose only when `value` empty; autofill category-swap keeps nonempty cells |
| FR-3958 forensics | All available snapshots post-08:11Z show blanks — **not recoverable; do not invent** |

## PR #123 review-guard closure — STOP for Technical PM (2026-10-28)

Technical PM reviewed clean PR #123 @ `43c8d376` → **HOLD — one focused P0 guard correction**. Prior invalidation/fingerprint/reviewer work stood; this tip closes the fail-closed source-pack guards.

### Guard correction (this tip)

| Control | Behavior |
|---|---|
| Run stage | `TechpackAIRun.stage` is authoritative (`professional` required). Disallowed stages (`basic`, `generate`, …) **fail closed** even for same-user/same-draft runs — no nested silent continue |
| Legacy blank | Empty stage allowed **only** when draft `ai.last_mode=professional` + `ai.last_run_id` matches the artifact run + run `completed` |
| Current source pack | Artifact `run_id` must equal draft `ai.last_run_id` (historical non-current Professional runs cannot dirty the pack) |
| Outfit reference | Artifact must appear in current garment illustration refs (unreferenced rows cannot invalidate) |
| Negatives | Non-Professional run · historical non-current run · unreferenced illustration — all 422, no revision bump |
| Positives | Valid Professional pathway + legacy blank-with-evidence preserved; PDF A→review→B / idempotent / history / zero-provider unchanged |

### Prior clean-replacement context (still in tip)

Technical PM reviewed prior PR #122 @ `8794583f` → **HOLD / CHANGES REQUIRED**. This clean replacement branch answers those P0/P1 items without private artifacts in git history.

### Owner smoke evidence still true (production, unchanged)

| Item | Result |
|---|---|
| Login after FE API-base fix | **PASS** |
| Reopen FR-3958 + Update PDF (No AI) → Rev **2** | **PASS** — 15p, `$0` assembly, source 250¢, same 7 images as Rev 1 |
| Paid provider calls | **0** |
| Source AI run / Rev 1 PDF | **Unchanged** (run `6b3bf6c3…`, export `b2a1922a…`) |
| Current export | Rev 2 `d19a5d0c…` still embeds wrong shorts detail (`7298860c…`, `proposed`) |

### PDF QA failures (Rev 2) — still open in production

| Sev | Defect |
|---|---|
| **P0** | Shorts detail page shows purple hoodie construction (artifact `7298860c…`) |
| **P1** | Outfit-level color list printed as garment color; layout/legend/provenance honesty |

### Clean replacement — what changed (NOT deployed)

| Item | Detail |
|---|---|
| Branch / PR | `cursor/web-techpack-pdf-qa-clean-77c6` · [#123](https://github.com/perielad2-netizen/FashionRise/pull/123) — descendant of prod BE `005034d5` (+ deploy docs); no private PDF/PNG/QA JSON in commits |
| Supersedes | Prior PR #122 / `cursor/web-techpack-pdf-qa-77c6` @ `8794583f` (private blobs in history — do not merge) |
| P0 review→PDF | `record_owned_artifact_review`: auth ownership checks → audit decision with **server-derived** `reviewer_user_id`/`username` → atomic `dirty_since_generation` + `outdated_export_id` + revision bump + `artifact_review_version` |
| P0 fingerprint | `_pdf_only_content_fingerprint` includes authoritative `TechpackAIArtifact` review tokens so PDF-only cannot reuse a pre-review export |
| P0 bytes | Illustration storage + historical PDF A preserved; **never** auto AI |
| P0 FE CTA | After review, GET draft shows `dirty_since_generation=true` → existing FE shows **Update PDF (No AI)** |
| P0 generic review API | `POST /techpacks/artifacts/{id}/review` — no hardcoded FR-3958 IDs in product modules; FR-3958 mark stays a bounded operator workflow after BE deploy |
| P0 git hygiene | Sanitized synthetic fixture UUIDs only; private offline evidence under `/opt/cursor/artifacts/fr3958-pdf-qa-clean/` (not in git) |
| P1 reviewer | No client `operator` field; identity from auth principal; auditable `operator_decisions` / `artifact_review_decisions` |
| P1 reapprove | Rejection and reapproval both reconcile `preview_include` / inclusion status |
| P1 colors | Live Garment color rows assert Lavender/purple + golden yellow; historical raw-color notes are not treated as live garment color |
| Private offline PDF | 14 pages · DESIGN CONCEPT · hoodie detail included · shorts detail EXCLUDED · purple+yellow colors · pdf_only `$0` / source 250¢ · **0** paid AI |

### Gates

| Gate | Result |
|---|---|
| `test_techpack_pdf_only_update` + `test_techpack_manufacturing_ready` + `test_techpack_p0_reliability` | **69 passed** (includes 3 negative + 1 legacy-blank guard tests) |
| Review→rebuild regression (wrong shorts art → reject → Update CTA → new PDF B excludes art; idempotent repeat; concurrent assembly; historical A; zero provider) | **PASS** |
| Guard negatives (non-Professional / historical / unreferenced) + legacy blank Professional evidence | **PASS** |
| Ruff F401/F821 on amended BE modules | **clean** |
| mypy `techpack_manufacturing` / schemas / routes | **clean** |
| mypy `techpack_service.py` | ~65 pre-existing union noise (no new blocker class) |
| Private offline FR-3958 PDF + page rasters + report | **PASS** @ `/opt/cursor/artifacts/fr3958-pdf-qa-clean/` |
| Production FE/BE/Alembic | **Preserved** — no deploy this turn |

### Sibling Issue #124 PRs (isolated — not this deploy)

| PR | Scope | Tip |
|---|---|---|
| [#126](https://github.com/perielad2-netizen/FashionRise/pull/126) FE measure decimal | `cursor/web-techpack-measure-decimal-77c6` | `bfbdd03f` |
| [#125](https://github.com/perielad2-netizen/FashionRise/pull/125) BE fidelity (closure/gradient) | `cursor/web-techpack-fidelity-b9f9-77c6` | `05118592` |

### Blocked / exact proposed deployment sequence (after Technical PM accept)

1. **Do not deploy** until acceptance. Do not rewrite historical exports. Do not run paid AI.
2. Controlled **BE + worker** deploy of this clean tip (force-checkout on VPS from `005034d5` lineage — **not** a blind GitHub merge into a stale PR base). FE stays **`13b26c3a-apifix`**. Alembic stays **`011`**.
3. Authenticated owner (or approved operator workflow) `POST /techpacks/artifacts/{7298860c…}/review` with `rejected_category_mismatch` — server dirties draft; FE shows **Update PDF (No AI)**.
4. Owner runs **Update PDF (No AI)** → new current PDF B excludes wrong shorts art; Rev 2 / Rev 1 remain downloadable; readiness DESIGN CONCEPT; assembly `$0`.
5. Rollback BE+worker → **`005034d5`** if needed. FE rollback → `69b83c01` only if FE regresses (unchanged by this PR).

## Completed-look UX + Update PDF (No AI) — deployed baseline (2026-10-28)

| Item | Detail |
|---|---|
| FE PR #120 | Deployed as **`13b26c3a-apifix`** (API-base fix-forward after missing `VITE_API_BASE_URL`) |
| BE PR #119 tip | Production **`005034d5`** (artwork provenance gate + docs) |
| Paid AI | **0** on PDF-only path |

### PR #119 artwork provenance / ownership gate (live)

| Control | Behavior |
|---|---|
| Source run | Owned completed Professional `TechpackAIRun` only |
| Illustrations | Server-owned `TechpackAIArtifact` rewrite before PDF assembly |
| Cost honesty | `assembly_cost_usd_cents=0` vs `source_run_cost_usd_cents` (QA branch also stamps PDF body) |

## PR #118 controlled deployment (2026-10-28) — STOP

Technical PM **ACCEPTED** manufacturing foundation. Deployed tip `2c8cb88e1571b01bd7ae6079e0543ddd754bfc7f` (reviewed closure `9ae1ead2` + docs/ruff tip commits) from production baseline `7af9c809` — **not** a blind GitHub merge into the stale PR base.

| Item | Detail |
|---|---|
| Lineage | `7af9c809` → … → `9ae1ead2` → tip `2c8cb88e` (ancestor-descendant; BE/docs only; no FE / no Alembic) |
| Deploy path | VPS `/opt/fashionrise/src` force-checkout tip · write `APP_REVISION`/`REVISION` · clear `__pycache__` · restart `fashionrise-api` + `fashionrise-ai-worker` |
| Deploy time | 2026-10-28 **12:08 Asia/Jerusalem** (10:08 UTC) |
| Health | `/health` ok · `/ready` database ok · both units **active** |
| Backup | `/var/backups/fashionrise/techpack-mfg-ready-deploy-20261028T100449Z/` (env, db dump/SQL, PDF meta, prior services) |
| Rollback | `…/ROLLBACK.sh` → **`7af9c809`** + restart API/worker |
| Pre-deploy gates | **46 passed** (`test_techpack_manufacturing_ready` + V2 PDF fixtures + P0 reliability) · ruff clean on `techpack_manufacturing.py` · mypy clean on `techpack_manufacturing.py` |
| Alembic | **`011`** confirmed post-deploy |
| Limits | `$50` ceiling · `$8`/run · `$20`/user/day · **6** images/run — confirmed unchanged |
| FR-3958 | Live draft assess → **`DESIGN_CONCEPT`** · **22** blocking/unresolved manufacturing issues (sample size, POM bands, ease, materials, closures, construction, unverified detail art, etc.) |
| Historical preserve | FR-3958 export `b2a1922a…` (10p / 13 366 568 B) + FR-D47D exports `07c5e48a…`/`cffdfb8a…`/`d1478343…` byte+page match backup; Download associations unchanged; offline PdfReader validation only (**no** live provider / regen) |
| Paid AI | **0** — no enqueue, no Professional generation, no historical PDF rewrite |
| FE | **Unchanged** at `69b83c01` |
| Blockers | FR-3958 remains DESIGN CONCEPT until designer confirms POMs/materials/closures/construction/sample size. No paid Professional regen authorized. |
| Exact next action | Owner/PM: hard-refresh FE; confirm Download still serves preserved FR-3958 / FR-D47D PDFs. Do **not** authorize paid regen unless explicitly scoped. Rollback if needed via backup `ROLLBACK.sh`. |

## Manufacturing-ready Tech Pack foundation (2026-10-28) — accepted & deployed

| Item | Detail |
|---|---|
| Trigger | FR-3958 (purple zip hoodie + yellow shorts) failed sample-development acceptance: implausible POMs, color-list “fabrics”, boolean closure, cross-garment detail sheet, readiness overstated by AI completion |
| Branch / PR | `cursor/web-techpack-mfg-ready-77c6` · [#118](https://github.com/perielad2-netizen/FashionRise/pull/118) · deployed from lineage `7af9c809` |
| Production | **Deployed** — FE `69b83c01` · BE+worker **`2c8cb88e`** · Alembic `011` · ceiling `$50` |
| Paid AI | **0** — offline fixtures + Mock paths only; existing FR-3958 / FR-D47D exports preserved |
| P0 Measurement integrity | Category-aware POM bands + body-vs-finished ease checks; contradictions flagged **NEEDS REVIEW** (values not silently corrected); sample size required |
| P0 Readiness levels | `DESIGN CONCEPT / DRAFT` · `SAMPLE-DEVELOPMENT READY` · `PRODUCTION APPROVED` (never auto). AI completion ≠ sample-ready |
| P0 Artifact quality | Cross-garment detail rejection; originals preserved; corrected preview excludes mismatches (no substitution, no regen) |
| P1 Materials / PDF | Color vs shell vs composition vs stretch/GSM; boolean closures normalized; larger detail sheets; no Piece A/B/C cutter rectangles; honest “no sewing pattern supplied” |
| Offline evidence | Fixture `backend/tests/fixtures/fr_3958_manufacturing_spec.json` · preview `backend/artifacts/manufacturing_previews/FR-3958_manufacturing_preview.pdf` |
| Tests | `test_techpack_manufacturing_ready.py` + V2 PDF fixtures + P0 reliability |
| Blockers for SAMPLE-READY on FR-3958 | Missing sample size; hoodie length 110 cm vs hip-length; shorts inseam 80 cm; waist 75 vs body 90 without stretch; zero-ease hip/chest with relaxed fit; shell/closure unconfirmed; shorts detail mismatch |
| Exact next action | Superseded by controlled deployment section above. |

## PR #118 PM amendment — CHANGES REQUIRED (2026-10-28) — STOP for acceptance

Technical PM reviewed `bfaf4651` and required fail-closed readiness, conservative artwork review, PDF/BOM fixes, and **real** private FR-3958 visual verification (not 1×1 / artifact-ID-only).

| Item | Detail |
|---|---|
| Parent review commit | `bfaf4651` |
| Amendment SHA | `c411ed17e3bf46e43b866738d85a60ad1f239aec` |
| Amendment branch / PR | `cursor/web-techpack-mfg-ready-77c6` · [#118](https://github.com/perielad2-netizen/FashionRise/pull/118) |
| Production | **Unchanged** — FE `69b83c01` · BE+worker `7af9c809` · Alembic `011` · ceiling `$50` · **no deploy** · **no migration** · **no historical export replacement** |
| Paid AI | **0** |
| Fail-closed readiness | `assess_manufacturing_readiness()` enforces category POMs + designer confirmation for finished measurements, fit/ease, materials, closures, construction, tolerances, conflict resolution. Checked QC checklist alone is **insufficient**. Never auto `PRODUCTION_APPROVED` |
| Artwork policy | Unverified detail art remains reviewable (`include=True`) but `manufacturing_evidence=False`. Artifact↔piece IDs / analysis text are **not** pixel proof. Rejected shorts detail stays excluded; originals preserved |
| PDF / BOM | `_SizedImage.wrap()` recomputes from immutable intended size; detail sheets on dedicated pages; BOM color-list rows → `Shell fabric — NOT CONFIRMED` (composition not invented); pattern review labels humanized |
| Offline tests | Negative incomplete trousers + hoodie → `DESIGN_CONCEPT`; positive complete confirmed trousers → `SAMPLE_DEVELOPMENT_READY` + `production_approved=False`; unmarked wrong-garment detail stays unverified and blocks sample-ready |
| Private visual QA | Real Magic `3958812c…` (1024×1536) + six stored artifacts from run `6b3bf6c3…`. Private PDF 14 pages rendered. Evidence under agent artifacts `fr-3958-mfg-private-qa/` (**not** committed to GitHub) |
| Private QA results | Hoodie/shorts flats PASS · hoodie detail readable + UNVERIFIED banner PASS · rejected shorts detail excluded PASS · BOM NOT CONFIRMED PASS · measurement warnings PASS · readiness DESIGN CONCEPT PASS |
| Known limitations | No automatic image-pixel garment classifier (conservative unverified state instead). Proposed backs remain unverified. FR-3958 still blocked for SAMPLE-READY until designer confirms POMs/materials/closures/construction/sample size |
| Exact next action | Superseded by readiness-gate closure below. |

## PR #118 readiness-gate closure (2026-10-28) — STOP for PM acceptance

Technical PM CONDITIONAL PASS on `c411ed17` with **deployment HOLD** pending fail-closed closure items.

| Item | Detail |
|---|---|
| Parent amendment | `c411ed17` |
| Closure tip | `9ae1ead23fe1d58ed612c1f48c57165fb40ae4a3` |
| Production | **Unchanged** — FE `69b83c01` · BE+worker `7af9c809` · Alembic `011` · ceiling `$50` · **no deploy** · **no migration** · **no historical PDF rewrite** |
| Paid AI | **0** |
| Outfit integrity | Empty / malformed / duplicate-id / unconfirmed-category outfits cannot reach SAMPLE-DEVELOPMENT READY |
| Provenance ≠ approval | `source=designer` alone is insufficient. Required POMs/materials/fit/closure/construction/tolerances need meaningful values **and** explicit confirmation; `review_status=open` / `needs_review` remain unconfirmed |
| Measurement exceptions | Narrow evidence-backed exceptions must match `code` + `piece_id` + `pom` + current `value_cm` (+ revision when set) with rationale; blanket `approve_all` rejected. Unmatched conflicts stay blocking |
| Mypy | `techpack_manufacturing.py` — **0 errors** (`mypy --follow-imports=skip`; no broad type suppression) |
| Tests | Prior suite preserved + new regressions (empty outfit, open-review designer provenance, scoped exception positive/negative) → **46 passed** with V2 PDF + P0 reliability |
| Private visual QA | Prior real-image 14-page FR-3958 evidence retained under agent artifacts (not in GitHub) |
| Known limitations | No automatic image-pixel garment classifier. Proposed backs unverified. Exception path covers measurement findings only (not materials/artwork). FR-3958 remains DESIGN CONCEPT until designer confirms fields |
| Exact next action | **STOP** for Technical PM acceptance of closure SHA. **Do not deploy.** |

## OWNER ACCEPTANCE PASS — Measurements & Details (FE)

Owner PASS on FE `69b83c01` for idle editor, Done save, reopen persistence, Generate-not-stale-Download after edit with existing Professional PDF.

## PR #116 Owner Acceptance PASS — Professional reliability

PM/owner acceptance **PASS** for PR #116 reliability work (structure gates, artifact binding, fair image budget, dirty invalidation, pattern honesty, fingerprint v2). Production baseline: FE `69b83c01` · BE/worker `0815433b` · Alembic `011`.

## PR #115 Professional quality audit — PM accepted

Evidence-only audit (`docs/TECHPACK-PROFESSIONAL-QUALITY-AUDIT.md`). Decision **NEEDS IMPROVEMENT**. Kept intact as historical evidence.

## FR-D47D controlled Professional validation — preflight (2026-10-28)

| Item | Detail |
|---|---|
| Mode | **Read-only preflight only** — no Generate, enqueue, paid OpenAI, PDF regen, or deploy |
| Target | Style **FR-D47D** · draft `6bc071d3…` · title “Look · Oct 26, 2026” |
| Structure | **2 pieces** — `top` (`piece-2df509ce`, label Top) + `trousers` (`piece-e51dce19`) · `piece_count=2` · not inconclusive |
| Magic | Front/look job present, completed, source image resolvable (~1.2 MB) · **no back** Magic |
| Historical PDF | Professional export `cffdfb8a…` · **`piece_count=1`** · still referenced as current `ai.export_id` · private file **present** |
| Dirty / Download | **`dirty_since_generation=false`** → UI would still treat one-piece pack as current Download |
| Active jobs | **None** (no queued / running / reconciliation_required) |
| Image plan (FE `propose_back:true`, max 6, no back) | Per garment: `flat_front` + `flat_back_proposed` + `detail_callouts` · pattern sheets skipped · **6 images** |
| Estimator | Deployed `estimate_professional_cents` → **413–796¢ (~$4.13–$7.96)** · within `$8`/run · operator remaining ~`$10.45` · user day remaining `$20` · **not a final charge guarantee** |
| Fingerprint | **v2 active** on code |
| Decision | **NO-GO** |
| Blockers | (1) Historical one-piece PDF still current Download / not marked dirty. (2) Legacy completed run has no structure/input fingerprints → `run_matches_draft_structure` would **reuse** that one-piece completed run instead of authorizing a new two-piece paid generate. |
| Paid AI | **0** |

### Exact next action (owner / PM) — superseded after hotfix

Preflight blockers (1)–(2) addressed by the historical-PDF validity maintenance below. Paid Generate remains **blocked** until an explicit single paid-run authorization is issued.

## FR-D47D historical PDF validity & reuse hotfix (2026-10-28)

| Item | Detail |
|---|---|
| Branch / PR | [`#117`](https://github.com/perielad2-netizen/FashionRise/pull/117) · `cursor/web-techpack-hist-pdf-validity-77c6` · base PR #116 tip `0815433b` |
| Commit / deploy | **`7af9c809`** · API + AI worker restarted · health OK |
| Root causes (preflight NO-GO) | (A) Live 2-piece FR-D47D still had `dirty_since_generation=false` with 1-piece export as current Download. (B) Legacy completed run without fingerprints: `run_matches_draft_structure` returned **True** → unsafe `reused_completed`. (C) FE idempotency `one-tap-{draft}-r{rev}` could replay the stale completed run. |
| Fix A | Authoritative `professional_pack_is_current_for_draft` + export `piece_count` contradiction; idempotent `reconcile_professional_export_validity` on GET draft / latest-run / enqueue |
| Fix B | `run_matches_draft_structure` **fail-closed** without positive fingerprint/piece_ids; reuse requires current pack evidence; never clear dirty for legacy mismatch |
| Fix C | Idempotency collision scopes a structure-bound key (`#s:{fp}`) for a new authorized intent; latest-run sets `pdf_ready=false` / `current_for_draft=false` while `historical_pdf_ready` remains |
| Offline tests | MockProfessionalProvider · `test_techpack_p0_reliability` + `pdf_ready_binding` **27 passed** · **$0** provider |
| Production verify (FR-D47D `6bc071d3…`) | GET reconcile → `dirty_since_generation=true`, `outdated_export_id=cffdfb8a…`, revision still **1**; export file **7,585,753** bytes intact; legacy run `72d563cc…` completed / cost **165¢** unchanged; `run_matches_draft_structure=false`; latest-run `pdf_ready=false` / `current_for_draft=false` / `historical_pdf_ready=true`; **0** queued/running; second reconcile write **false** |
| Migration | **None** — Alembic **`011`** |
| Paid AI | **0** |
| Backup / rollback | `/var/backups/fashionrise/techpack-hist-pdf-validity-deploy-20261028T071542Z/` · `ROLLBACK.sh` → **`0815433b`** |
| Post-fix preflight | **GO** for Download/reuse gates on FR-D47D. **Not** authorization to spend. |
| Exact next owner action | **Superseded** — owner issued single-run authorization; see live validation section below. |

## FR-D47D first authorized live Professional validation (2026-10-28)

| Item | Detail |
|---|---|
| Authorization | **EXACTLY ONE** paid Professional run · draft `6bc071d3-e150-44bb-af3f-f0fed632d5fc` · style **FR-D47D** · owner-approved · no retries · no Magic · no budget/config/code changes |
| Runtime lineage | FE `69b83c01` · BE+worker **`7af9c809`** · Alembic **`011`** · PR #116 PASS · PR #117 hotfix live |
| Pre-submit | Dirty=true · pieces `piece-2df509ce` top + `piece-e51dce19` trousers · Magic front resolves · no back · fingerprint **v2** · plan **6** images · estimate **413–796¢** · user-day remaining `$20` · allowlisted · **0** active runs · **GO** |
| Submit | Authenticated one-tap `generate-professional` · HTTP **202** · status **queued** (not reused) · auth TS **2026-10-28T07:40:53Z** · idempotency prefix `owner-auth-fr-d47d-live-20261028T074053Z-…` |
| New run | **`cb4a8efc-ff36-45ca-9751-97d8ce10ba0e`** · input fingerprint version **2** · planned images **6** · estimate **796¢** |
| Outcome | **completed** · `pdf_ready=true` · `current_for_draft=true` · progress ready · ~3.5 min wall time |
| New export | **`d1478343-205e-4f03-b964-3bd477281099`** · piece_count **2** · **9** pages · **10,659,152** bytes · Professional |
| Artifacts | 6/6 bound to correct piece IDs: front + proposed back + detail for top and trousers |
| Historical PDF | `cffdfb8a…` **intact** (**7,585,753** bytes, piece_count=1) · retained as `outdated_export_id` / prior run `72d563cc…` |
| Internal cost | Estimated **796¢** · recorded actual **250¢ ($2.50)** · billable status **recorded on run** |
| Provider calls (worker logs) | **2**× `chat/completions` (vision) · **6**× `images/edits` · all HTTP 200 · no failed paid sections (pattern sheets budget-skipped only) |
| OpenAI billing | Production key is `sk-proj-…` (project key). Dashboard credit balance **not readable** via API key (session/browser required). Owner starting screenshot **$14.17** (~09:36 Asia/Jerusalem). Ending balance **not captured here** — owner to supply post-run screenshot. Auto-reload settings **not modified**. Org/project title match to screenshot: **unconfirmed** (no org headers on Models API; balance comparison may not measure this run until owner confirms). |
| Private preserve | `/var/lib/fashionrise/storage/private_qa/fr-d47d-live-validation-20261028T0741Z/` (+ backup mirror under `/var/backups/fashionrise/…`) — Magic front, 6 flats, new+historical PDFs, meta. **Not** committed to GitHub. |
| Visual QA | **Ready for human review** · **NOT passed** merely because the run completed |
| Quality blockers | Human visual review of tunic/trousers flats, proposed backs, detail sheets, and 9-page PDF still required |
| Second run | **None** · STOP after this run |
| Exact next owner action | (1) Open the new PDF/export `d1478343…` and perform visual QA. (2) Capture OpenAI billing balance screenshot and compare to `$14.17`. (3) Do **not** authorize another paid generate unless a separate explicit authorization is issued. |

## Operator spend ceiling raise — $15 → $50 (2026-10-28)

| Item | Detail |
|---|---|
| Reason | UI showed “Operator techpack AI spend ceiling reached” because recorded spend **$7.05** + two-garment estimate upper **$7.96** ⇒ **$15.01** vs old ceiling **$15** |
| Change | **Only** `TECHPACK_AI_SPEND_CEILING_USD=50.00` (was `15`) |
| Unchanged | `TECHPACK_AI_MAX_USD_PER_RUN=8` · `TECHPACK_AI_MAX_USD_PER_USER_DAY=20` · `TECHPACK_AI_MAX_IMAGES_PER_RUN=6` · models · enablement/allowlist · all other env |
| Code / migrate / FE | **None** — env-only · no merge · no paid enqueue |
| Runtime after restart | API+worker healthy · settings report ceiling **50.0** · max run **8** · user day **20** · images **6** |
| Read-only gate check | Recorded spend **705¢** + estimate hi **796¢** = **1501¢** ≤ ceiling **5000¢** · challenge `ai_enabled=true` · message no longer ceiling-blocked |
| Paid AI this change | **0** |
| Backup / rollback | `/var/backups/fashionrise/techpack-spend-ceiling-50-deploy-20261028T080703Z/` · `ROLLBACK.sh` restores prior `.env` (ceiling `$15`) and restarts API+worker |
| Safety | Ceiling must not be set to `0` (disables Professional under current implementation) |
| Exact next owner action | Manual Generate AI PDF from the web UI for additional designs as desired; agent does not enqueue paid runs. |

## Professional Tech Pack P0/P1 reliability — PR #116 (landed)

| Item | Detail |
|---|---|
| Branch / PR | [`#116`](https://github.com/perielad2-netizen/FashionRise/pull/116) · `cursor/web-techpack-p0-reliability-be-77c6` |
| Initial deploy | **`bae05c56`** · backup `techpack-p0-reliability-deploy-20261027T201322Z` · rollback → `732bda9f` |
| Amendment deploy | **`270e87e2`** · backup `techpack-p0-amend-deploy-20261027T205258Z` · rollback → `bae05c56` |
| Fingerprint v2 deploy | **`0815433b`** · backup `techpack-p0-fpv2-deploy-20261028T052414Z` · rollback → `270e87e2` |
| Scope | Structure validation; remove `pieces[0]` fallback; fair image budget; repair invalidates Download; pattern `proposed_unverified`; PDF REVIEW; inconclusive reject; input fingerprint v2 |
| Workflow | Unchanged: **Generate AI PDF → Wait → Download PDF** |
| Migration | **None** (Alembic `011`) |
| Owner acceptance | **PASS** |
| Offline tests | **51 passed** (MockProfessionalProvider, $0) |

---

## Historical handoff archive (preserved)

> The following sections are preserved from prior status revisions so project decisions and milestones are not lost. Prefer the **Last updated** / production table above for current truth.

### Archived snapshot — techpack-quality-audit / owner PASS era

# FashionRise — project status & session handoff

**Purpose:** Single page to align **new chat sessions** and humans on **what exists**, **where it lives**, and **what to do next**.
**Maintenance:** After each meaningful milestone, update the **last updated** line, **milestone table**, and **suggested next steps**.

**Last updated:** 2026-10-27 (**OWNER ACCEPTANCE PASS** — Measurements & Details FE `69b83c01` / PR #114. Professional AI Technical Pack **quality audit complete** → **NEEDS IMPROVEMENT**. Backend **`732bda9f`** / worker unchanged / Alembic **`011`**. **0 paid AI calls**. Docs-only analysis branch — **no deploy**.)

**Phase:** Protected family beta. Create Real Design main workflow unchanged. Editor acceptance closed; Professional PDF quality gated on PM review of audit evidence.

**Production (`https://fashionrise.app`, behind Cloudflare Access + Authenticated Origin Pulls):**

| Layer | Revision |
|---|---|
| Frontend (`web-ui`) | **`69b83c01`** — Nginx `root` → `/var/www/fashionrise/current` → `releases/69b83c01`. Done closes only after latest editable snapshot is clean. Prior: `af1ddbb5` (PDF validity) ← `31c1de01` (quiet autosave) ← `ce752b43` (#113). |
| Backend (FastAPI + PostgreSQL) | **`732bda9f`** — **unchanged** (hash-matched `techpack_pdf.py` / `techpack_ai_professional.py` during audit). |
| AI worker | Standalone `fashionrise-ai-worker` — **unchanged** · `OPENAI_MODEL=gpt-6-luna` |
| Database | `fashionrise_beta` — Alembic **`011`** (no migration) |
| Nginx | `root /var/www/fashionrise/current;` · `index.html` / `version.json` / `sw.js` no-store |
| Deploy backup | `/var/backups/fashionrise/done-race-fe-deploy-20261027T164012Z` (rollback → prior FE `af1ddbb5`) |
| AI spend | Ceiling **`$15`**, max **`$8`/run**, **`$20`/user/day**, allowlist **3**, `OPENAI_REASONING_EFFORT=none`. **Audit paid calls: 0.** |

## OWNER ACCEPTANCE PASS — 2026-10-27 (Measurements & Details)

Owner confirmed PASS on production FE **`69b83c01`** for all four scenarios:

1. Open editor without flicker / write loops.  
2. Edit a measurement and close with Done.  
3. Reopen and confirm the saved value.  
4. Edit a design that already has a Professional PDF → UI shows **Generate AI PDF** (not stale Download).

Quiet autosave + PDF validity + Done/save race (PR #114) remain LIVE. **No further editor work** unless a new regression appears.

## Professional AI Technical Pack quality audit — 2026-10-27 (docs only)

| Item | Detail |
|---|---|
| Deliverable | [`docs/TECHPACK-PROFESSIONAL-QUALITY-AUDIT.md`](./TECHPACK-PROFESSIONAL-QUALITY-AUDIT.md) |
| Tip |  |
| Branch | `cursor/techpack-quality-audit-77c6` (from docs tip `ac76632a` / production FE lineage) |
| Decision | **NEEDS IMPROVEMENT** |
| Real PDFs inspected | **FR-7182** (pink striped dress, V3.1), **FR-D47D** (Magic = tunic+trousers but PDF = 1× dress), **FR-CF5A** (burgundy slip, V2 footer) |
| Not evaluable | **FR-3958** lavender hoodie + yellow shorts — draft only, **no** Professional export |
| Offline tests | `test_techpack_v3_professional` + `v31_one_tap` + `v2_pdf_fixtures` + `provenance` → **20 passed** (mock provider, $0) |
| Top P0 | Multi-piece identity collapse (FR-D47D); AI pattern rows labeled `approved_template` |
| Top P1 | silk≠cotton without REVIEW on stored FR-CF5A; sleeveless + sleeve length 60; long-sleeve assumption on ¾ tunic |
| Safety | No production code/deploy/migration; private PDFs not committed; **0 paid AI** |
| Blocked / unapproved | Fixes, regenerations, deploys, merges of stale `main` / unrelated PRs |

### Exact next action (PM)

1. Read the audit scorecards (especially FR-D47D P0 and FR-7182 `approved_template`).  
2. Choose: **targeted fix** (multi-piece generate gate + review_state default + PDF REVIEW/sleeve guards) **or** owner visual review of FR-7182 pages 1/3/5 first.  
3. Do **not** authorize paid Professional regenerations until that choice is explicit.

## Quiet autosave + PDF validity + Done race (2026-10-27) LIVE — owner accepted

| Item | Detail |
|---|---|
| PR / branch | FE [#114](https://github.com/perielad2-netizen/FashionRise/pull/114) · `cursor/web-techpack-autosave-quiet-77c6` · tip `69b83c010391cb14d937a0ba777a77a8de87be73` |
| Quiet autosave | Dirty-only 700ms debounce; no Saving/Saved chrome; fingerprint omits server `ai` |
| PDF validity | Local edits + server `dirty_since_generation` hide Download; sync after PATCH without form replace |
| Done-race root cause | `if (saved || !isEditorDirty())` closed after an older successful PATCH even when newer mid-flight edits remained |
| Done-race fix | Non-overlapping flush loop closes only when fingerprint is clean and saves settled; re-entry guard on Done/Escape; failure keeps editor + Retry |
| Tests (StrictMode, 390/768/1366) | Clean Done **0** PATCH; dirty Done **1**; A→Done→edit B mid-flight → B persisted before close (`maxInFlight=1`); B fail → stay open; Done during background PATCH → no overlap; repeated Done/Escape → no duplicate writes; prior quiet/PDF suites green (**73** related tests) |
| Production verify | `current`→`69b83c01`; version.json full SHA; health/ready OK; BE still `732bda9f` |
| Safety | FE-only; BE/worker untouched; **0 paid AI** |
| Owner acceptance | **PASS — 2026-10-27** |
| Rollback | `ln -sfn /var/www/fashionrise/releases/af1ddbb5 /var/www/fashionrise/current && nginx -t && systemctl reload nginx` · or `done-race-fe-deploy-…/ROLLBACK.sh` |

## V3.1 — what shipped (2026-10-27)

| Item | Detail |
|---|---|
| Measurement reset root cause | `MeasurementsSheet` effect depended on `groups` (rebuilt whenever `pieces` identity changed on each keystroke) and reset `groupIndex` to Body |
| Measurement fix | Track active group by stable id; init only on open / draftKey / initialGroupId; clamp if piece removed |
| Mobile tests | Vitest keystroke harness: Finished Dress + Preferences + two-piece outfit; focus retained |
| Generation UX | Single **Generate AI PDF** — no Basic pack / cost-estimate / confirm checkbox in the active workflow |
| Server intent | One-tap mints confirm token server-side; allowlist, ceilings, concurrent, idempotency preserved |
| Progress | Named phases on `TechpackAIRun.request.progress`; overlay + `GET …/ai/latest-run` resume (no duplicate paid start) |
| PDF | Larger detail flats; material REVIEW (silk≠cotton); sleeveless sleeve/construction/inventory flags; `PROPOSED BACK — UNVERIFIED`; footer **Create Real Design V3.1** |
| Offline PDF / mock AI | BE `test_techpack_v31_one_tap.py` **6 passed**; V3 professional + provenance **13** with disposable `fashionrise_test` |
| Production smoke | Health/ready OK; OpenAPI exposes generate-professional + latest-run; Alembic `010`; version.json `9ba396a3` |

### Next recommended action (owner — Samsung)

1. Hard-refresh FashionRise (or clear site data once) → confirm App / Create Real Design build **`9ba396a3`**.
2. Open saved Magic look → Step 3 → Finished Garment → type several values → **must stay on Finished** (no jump to Body).
3. Step 4 → one tap **Generate AI PDF** → see Magic-style progress → PDF ready → Preview / Download (no second payment).
4. Review PDF for detail size, material REVIEW, sleeveless construction, proposed back label.
5. Report results; do not ask Cursor to re-run paid generate unless a real failure appears.

### Rollback (V3.1)

- FE: `ln -sfn /var/www/fashionrise/releases/cf2a31ac /var/www/fashionrise/current && nginx -t && systemctl reload nginx`
- BE: restore files from `/var/backups/fashionrise/v31-deploy-20261026T233003Z/` into `/opt/fashionrise/src/backend/…` and `systemctl restart fashionrise-api`
- DB dump retained at that backup path (prefer app rollback; no migration to reverse)

## CRITICAL fix — root causes (2026-10-26)

| Bug | Root cause | Fix |
|---|---|---|
| `OPENAI_REASONING_EFFORT is empty` on paid generate | `OpenAIProfessionalProvider.analyze_garment()` called `chat_completion_kwargs` without `reasoning_effort` | Pass `reasoning_effort=settings.openai_reasoning_effort` |
| Mobile measurements unusable on Samsung Internet | Nginx still served **`129e57dd`** (no Edit Measurements). Symlink `current`→`5f519734` was **not** the active root. Emulator shots of `5f519734` were mistaken for phone evidence. | Deploy `33230fa0` + set Nginx root + `current` to same release; auto-open sheet; value-first inputs |
| Step 4 AI hard to reach / errors buried | Form pane scroll not targeted; errors below outfit card | `scrollStageIntoView` on form pane; sticky AI error panel near controls |
| Caching / version identity | Stale Nginx root + no visible FE build id | Root aligned; `Build {sha}` in Create Real Design header; index no-cache |

### Failed AI run audit (read-only)

| Check | Result |
|---|---|
| Matching failed run | **1** with `OPENAI_REASONING_EFFORT is empty` |
| Status | `failed` |
| Cost recorded | **0¢** |
| Provider called | **false** / null (request construction failure — no vision request) |
| Artifacts | **0** |
| Draft preserved | **yes** (run did not mutate pack content) |
| Marked successful? | **No** — left failed |

### Verification matrix (do not conflate)

| Layer | Result |
|---|---|
| Unit / SDK-boundary tests (mocked OpenAI) | BE **42 passed** (SDK boundary + V3 + model migration); FE TechpackScreen+MeasurementsSheet **20 passed** |
| Emulator / headless Chrome 360/390/430 | Measurement sheet + Stage 4 pack UI screenshots under `/opt/cursor/artifacts/techpack-crit-fix/` — **simulated viewports only** |
| Production browser smoke (origin) | Health OK; Nginx root `33230fa0`; reasoning kwargs resolve to `none`; AI gates unchanged; Alembic `010` |
| Real Samsung Internet device | **Not exercised by Cursor** — left to owner |
| Owner acceptance | **Pending** |


## Mobile step modals (2026-10-26 night) LIVE

Owner Samsung recording showed step chips with forms buried under the look preview. FE PR [#101](https://github.com/perielad2-netizen/FashionRise/pull/101) `fd9718f3` deployed: tap step → full-screen modal (StageSheet 1/2/4, MeasurementsSheet 3). Nginx root + `current` = `fd9718f3`. BE still `186cac84` (reasoning_effort fix). **Owner Samsung re-check pending** — emulator screenshots are not phone acceptance.

### Next recommended action (owner)

1. Open FashionRise on Samsung Internet (normal or fresh tab).
2. Confirm Create Real Design header shows **Build 33230fa0** (Settings/About-equivalent on this screen).
3. Open an existing Magic look → Create Real Design → Step 3 → enter Waist/Height → Save & Done → reopen → confirm value persists.
4. Step 4 → select **AI Professional** → Get cost estimate → confirm checkbox → **Generate Professional Pack** (first paid test by owner).
5. Report illustrations / PDF back to ChatGPT.

### Rollback

`/var/backups/fashionrise/techpack-crit-fix-deploy-20261026T213807Z/ROLLBACK.sh` restores prior Nginx root `129e57dd` and prior BE service files. Prefer app-only rollback; DB dump retained but not preferred.

---

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

**P1 #51 — Fullscreen Hand→Pencil (ACTIVE HOTFIX):** After Full Screen Drawing → Hand pan/pinch-zoom → Pencil, fresh strokes are ignored until page refresh. **Root cause (proven):** `DrawingCanvas` window-pointer `useEffect` depended on `pointFrom`→`viewport`; pan/zoom rerenders remounted listeners and **cleared `gestureCooldownTimer` while leaving `gestureCooldown.current === true`**, so `onPointerDown` returned forever. **Fix:** long-lived window listeners via handler refs (deps: `immersive` only); cooldown timer cleared only on component unmount; clear pan state when leaving Hand. Regression Vitest suite added (controlled viewport React state). **No merge/deploy** until Technical PM review + post-deploy operator mobile/tablet acceptance.

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
| GitHub `main` | **`dfcaa609`** — WEB-V4I merged (PR #41 pose fidelity source present, BE not deployed) |
| Production frontend / backend / worker | **`4589a62d` / `6b253cb5` / `6b253cb5`** · Alembic **`005`** · Dual Magic BE **not** deployed |
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
| **P1 #51 Hand→Pencil immersive** | **Draft PR [#52](https://github.com/perielad2-netizen/FashionRise/pull/52)** — gesture cooldown stuck after viewport remount; FE-only; **STOP for PM** (priority over #42) |
| **Issue #42 / WEB-V4J Front-Back** | **DEPLOYED** drawing @ `4589a62d` + Stage B BE `6b253cb5`. Dual Magic **implementation ready** on PR [#70](https://github.com/perielad2-netizen/FashionRise/pull/70) + FE retry on [#69](https://github.com/perielad2-netizen/FashionRise/pull/69) — **not activated** (`DUAL_MAGIC=false`). |
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
- Home, Design Book, Discover, and future rail tools stay disabled. **My Looks is enabled.**

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

1. **Exact next action (owner):** On Android: My Looks → FR-7182 → Create Real Design → Step 3 **Edit Measurements** (full-screen sheet; empty OK) → Continue → Stage 4 select **AI Professional Technical Pack** (not Preview Basic) → Get cost estimate → confirm → **Generate Professional Pack** → review illustrations → **Export Professional PDF**. Send screenshots + PDF for quality review. Do **not** start monetization.
2. After owner visual review: tune prompts/limits only if FR-7182 flats fail source fidelity (deep V, long sleeves, fitted mini, diagonal pink/white stripes).
3. Repository reconciliation: keep production lineage PRs as cherry-pick sources; never force-merge unrelated old stacks into stale `main`.
4. **Do not auto-merge** docs draft PRs [#28](https://github.com/perielad2-netizen/FashionRise/pull/28)/[#36](https://github.com/perielad2-netizen/FashionRise/pull/36)/[#38](https://github.com/perielad2-netizen/FashionRise/pull/38)/[#44](https://github.com/perielad2-netizen/FashionRise/pull/44)/[#46](https://github.com/perielad2-netizen/FashionRise/pull/46).
5. **Operator residual:** expired Access session test (still PENDING).

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
| Outstanding | Production FE `dfcaa609`; **P1 #51 hotfix draft**; Issue #42 / V4J suspended; Magic pose Issue #39 / PR #41 not deployed |

## WEB-V4J Front/Back production release verification (2026-10-25)

| Check | Result |
|---|---|
| Preflight BE baseline | **PASS** — live `12f7acdf` (Stage A maint) before cutover; FE `a740a9b7`; Alembic `005`; api/worker/nginx/postgres active |
| Stage B BE deploy | **PASS** — `6b253cb52beb9524f976ba805049bf3de2506985`; no polish-dual in tree; `/health`+`/ready` ok; Alembic still `005` |
| FE deploy (PR #69 + Dual Magic gate) | **PASS** — `/var/www/fashionrise/releases/4589a62d`; `FRONT_BACK=true`, `DUAL_MAGIC=false`, `MAGIC_UI=true` |
| Dual Magic BE PR #70 | **NOT DEPLOYED** (held) |
| Front/Back smoke | **PASS** — female-straight Front draw → Flip → Back draw |
| Save / reopen | **PASS** — draft.v2 + saved design both sides ink preserved after refresh |
| Nine Back models | **PASS** — 9/9 `*-back.png` `image/png`; `female-atelier` Front-only (no real back PNG) |
| Existing Front Magic | **PASS** — Front-only still attempts `/ai/sketch/polish` (smoke-blocked; **0** paid jobs) |
| Dual Magic safely disabled | **PASS** — Back ink → “Front/Back Magic coming soon”; polish-dual requests **0**; API polish-dual **404** |
| Backup | `/var/backups/fashionrise/v4j-frontback-deploy-20261025T174543Z` |
| Unresolved | None for this scoped release. Dual Magic remains gated pending PR #70 authorize. |

## Undo→autosave conflict fix (2026-10-26)

| Check | Result |
|---|---|
| Root cause | Back undo emptied ink without `clearBackIntent` → BE OCC 409; stale in-flight draw save vs authoritative undo opened false Draft recovery |
| Fix | FE-only: stamp `clearBackIntent` on Back undo/redo empty; same-content + authoritative-match 409 ACK in `flushCloudSave` / `persistStudioDraft`; multi-tab foreign content still conflicts |
| Vitest | **29/29 PASS** (undoAutosave + frontBack + queue + draftPersistence) |
| Playwright persistence | Undo→Save Front **PASS** · Undo→Save Back **PASS** · multi-tab conflict **PASS** · `clearBackIntent` seen |
| Deployed FE | **`c99c2c86`** (`c99c2c86739f6a76d40231079bf1b861e83cbfca`) · PR [#79](https://github.com/perielad2-netizen/FashionRise/pull/79) |
| BE / worker / Alembic / flags | **Unchanged** (`c103ee8d` / `005` / Dual Magic ON) |
| Backup / rollback | `/var/backups/fashionrise/v4j-undo-autosave-fe-deploy-20261026T120935Z` → `db11bf66` |
| Paid AI | **0** |

## Magic polish + color-authority fix (2026-10-26)

| Check | Result |
|---|---|
| Regression | Alphabetical `shared_garment_spec` JSON truncated to 320 chars dropped `main_colors` after lengthy FE `details` |
| Fix | BE ordered whitelist serialization (`main_colors`/`materials` first; optional notes/details last; complete JSON only) + FE garment-spec color/cleanup locks |
| Prompt tests | Gray `#9CA3AF` authoritative in final `_build_image_prompt` Front/Back; largest patterned side payload ≤ 4500; Magic quality/coverage suites **PASS** |
| Deployed FE | **`ec0ad13a`** (`ec0ad13ae00d854d44a1bf3d6d8ee23364d56841`) · PR [#80](https://github.com/perielad2-netizen/FashionRise/pull/80) |
| Deployed BE/worker | **`18344e6a`** (`18344e6a444dae7aa06f36325bece139997cd44d`) · PR [#81](https://github.com/perielad2-netizen/FashionRise/pull/81) |
| Flags / Alembic | Front/Back **ON**, Dual Magic **ON**, pattern fidelity path live · Alembic **`005`** |
| Backup / rollback | `/var/backups/fashionrise/v4j-magic-polish-deploy-20261026T123621Z` → FE `c99c2c86` / BE `c103ee8d` |
| Paid Dual sample | **1** operation · Front job `378ed560…` + Back job `eda3327a…` · `image_inputs=1` each · **no retries** |
| Visual — invented colors | **PASS** (solid gray only; no pink/blue accents / decorative panels) |
| Visual — uneven strap cleanup | **PASS** (Front asymmetric drape normalized professionally; Back straps cleaned into intentional V/cord back) |
| Visual — render quality | **PASS** (polished non-photoreal fashion illustration retained) |
| Fabric patterns | **N/A** this sample (solid fill; no swatch). Prior pattern-fidelity path unchanged. |


## Create Real Design / techpack PDF (2026-10-26) DEPLOYED — Issue #83

| Field | Value |
|---|---|
| Scope | My Looks → Create Real Design editable tech-pack form → preview → authenticated PDF. Owner-scoped drafts independent of look delete. Every export **DRAFT / UNVERIFIED**. FR-5608 fixes: Page N of M, Height once, cutting reuses Magic looks. AI draft assist disabled. **0 paid AI**. No monetization. |
| BE | PR [#91](https://github.com/perielad2-netizen/FashionRise/pull/91) `b4a0976c` · Alembic `008` |
| FE | PR [#92](https://github.com/perielad2-netizen/FashionRise/pull/92) `3ef29bc4` · release `/var/www/fashionrise/releases/3ef29bc4` |
| Smoke | Authenticated create→export→PDF **PASS** (5 pages, ~3.3MB, DRAFT/UNVERIFIED, Height count=1) |
| Backup | `/var/backups/fashionrise/techpack-deploy-20261026T163802Z` |

## My Looks Delete (2026-10-26) DEPLOYED

| Check | Result |
|---|---|
| Scope | Permanent Delete Look (tombstone). Archive/restore unchanged. No PDF/#83, **0 paid AI**, no erasure of AI job image files. |
| BE | `DELETE /api/v1/looks/{id}` → `magic_look_meta.is_deleted`; excluded from list/get/patch; idempotent; cross-account 404 |
| FE | Card + detail Delete; ConfirmDialog cancel/busy/retry; reconcile 404/uncertain before success |
| Nginx | Looks `{uuid}` `limit_except GET PATCH DELETE` |
| Tests | BE pytest delete + nginx **PASS**; FE Vitest cancel/confirm/retry + looksApi **PASS**; tsc/build/SW **PASS** |
| Prod API smoke | **PASS** — single + dual delete, no resurrection, keep sibling, image retained, designs/my OK, cross-account 404 |
| Deployed FE | **`6be1cf2d`** · PR [#90](https://github.com/perielad2-netizen/FashionRise/pull/90) |
| Deployed BE | **`26a374d5`** · PR [#89](https://github.com/perielad2-netizen/FashionRise/pull/89) |
| Alembic | **`007`** |
| Backup / rollback | `/var/backups/fashionrise/my-looks-delete-deploy-20261026T160605Z` → FE `811ffc52` / BE `ba013fdf` |
| Limitation | Access UI not automatable from this agent; owner should click Cancel + Delete once in browser |

## My Looks — persistent Magic gallery (2026-10-26) DEPLOYED

| Check | Result |
|---|---|
| Scope | Owner-scoped gallery of completed Magic (`sketch_polish`) looks; Front/Back grouping; rename/favorite/archive; Magic **View in My Looks**. No PDF/#83, no Magic prompt/generation changes, **0 paid AI**. |
| Look identity | Dual: `magic_operation_id`; single: job id. Metadata in `magic_look_meta` (Alembic **006**). Images remain `ai_jobs` + storage files via auth `/ai/jobs/{id}/image`. |
| BE | `GET/PATCH /api/v1/looks` — pagination, search, All/Favorites/Archived; prefer successful image over failed retry; skip looks with missing files |
| FE | `/studio/looks` portfolio gallery + detail dialog; lazy auth thumbnails; Studio drafts untouched |
| Nginx | Exact `GET /api/v1/looks` + `GET\|PATCH /api/v1/looks/{uuid}` only |
| Tests | BE pytest looks + nginx allowlist **PASS**; FE Vitest looksApi/MyLooksScreen/MagicLookPanel/StudioPage **PASS**; tsc + build + SW safety **PASS** |
| Prod API smoke | **PASS** — historical+new synthetic looks, dual grouping, rename/favorite/archive/restore, cross-account 404, image owner-scope, designs/my healthy |
| Deployed FE | **`811ffc52`** · PR [#88](https://github.com/perielad2-netizen/FashionRise/pull/88) |
| Deployed BE | **`ba013fdf`** · PR [#87](https://github.com/perielad2-netizen/FashionRise/pull/87) |
| Flags / Alembic | Front/Back **ON**, Dual Magic **ON**, Magic UI **ON**, Registration UI **ON** · Alembic **`006`** |
| Backup / rollback | `/var/backups/fashionrise/my-looks-deploy-20261026T151741Z` → FE `129e57dd` / BE `108db149` (+ nginx restore; optional `alembic downgrade 005`) |
| Limitations | Cloudflare Access blocks unattended public browser automation from this agent; owner should confirm UI in Access session. Smoke-loopback FE root not switched (prod `fashionrise.app` was). |
| Paid AI | **0** |

## Issue #17 — Delete saved design (2026-10-26) DEPLOYED

| Check | Result |
|---|---|
| Scope | My Designs Delete + saved-only BE route + narrow Nginx DELETE allowlist. No PDF/#83, no Magic changes, no migration. |
| BE | `DELETE /api/v1/designs/saved/{id}` — private `fashionrise.saved_design.v1`/`v2` only; owner 404 cross-user; 422 working draft/unknown/damaged; generic `DELETE /designs/{id}` unchanged |
| FE | Accessible Delete on each valid card; permanent-delete confirm; Cancel no-op; offline/ambiguous reconcile; preview `release`; Studio draft untouched |
| Nginx | Exact saved DELETE proxied; generic designs DELETE denied at edge (`limit_except GET POST PUT`) |
| BE tests | `test_delete_saved_design.py` + nginx allowlist script **PASS** (owner V1/V2, cross-user, draft protect, nonexistent, unknown/damaged, siblings) |
| FE tests | `savedDesignsApi` + `StudioPage.designs` delete suite **PASS** |
| Prod API smoke | **PASS** — delete V2, keep V1, draft 422, cross-user 404, idempotent 404 |
| Browser smoke | **PASS** — save two → cancel → delete one → reload; remaining + working draft preserved |
| Owner production acceptance | **PASS** — 4 saved → 3 after delete; Studio working draft intact |
| Deployed FE | **`4095e0ac`** · PR [#86](https://github.com/perielad2-netizen/FashionRise/pull/86) |
| Deployed BE | **`108db149`** · PR [#85](https://github.com/perielad2-netizen/FashionRise/pull/85) |
| Flags / Alembic | Front/Back **ON**, Dual Magic **ON** · Alembic **`005`** |
| Backup / rollback | `/var/backups/fashionrise/issue17-delete-saved-20261026T134249Z` → FE `c052e075` / BE `18344e6a` |
| Paid AI | **0** |

## Issue #17 — post-release delete 404 hardening (2026-10-26) PREPARED — not deployed

| Check | Result |
|---|---|
| Production (unchanged) | FE **`4095e0ac`** · BE **`108db149`** · Alembic **`005`** · Dual Magic **ON** · Nginx saved-DELETE allowlist live |
| Owner acceptance of live Delete | **PASS** (4→3, draft intact) — feature not reimplemented |
| Exact fix | `deleteSavedDesign`: DELETE HTTP **404** no longer auto-success; reconcile via fresh `listMyDesigns` / `getDesign` using **raw** `row.id` + `user_id` (not `parseSavedDesign` success). Success only when deleted (204) or confirmed **absent**; if still present or verification unavailable → keep card + accurate error |
| Scope | FE-only (`savedDesignsApi.ts` + tests + status). No Magic / drafts / Front/Back / fabric / Nginx / BE |
| Tests | Vitest focused cases: 404+present (incl. unparseable raw id), 404+absent, 404+unavailable verification; delete suite still green (**47** in designs/api files) |
| Gates | oxlint warnings-only (pre-existing) · `tsc -b` PASS · production build + `check:sw` ok |
| PR status | [#86](https://github.com/perielad2-netizen/FashionRise/pull/86) OPEN / MERGEABLE vs `main` (lineage tip). [#85](https://github.com/perielad2-netizen/FashionRise/pull/85) OPEN / **CONFLICTING** vs stale `main` (BE already live at `108db149`) |
| Blockers | **STOP for review** — authorize FE-only hardening deploy before changing prod FE root |
| Next action | After approval: build PR #86 tip with current Vite flags → new `/var/www/fashionrise/releases/<sha>` → point FashionRise nginx `root` only → reload nginx → smoke one delete 404-reconcile path. Leave BE/Nginx allowlist/worker untouched |
| Paid AI | **0** |

## Changelog (handoff doc only)

| Date | Summary |
|------|---------|
| 2026-11-01 | **#135 Create My Croquis V5 photo-faithful proportions DEPLOYED:** tip `faa7d91d` / `faa7d91d47be433e6cfa771d5c8f9a1b744545b4` · croquis-lineart-v5 · image1 geometry / image2 style-only · no elongated silhouette · BE 42 mocked · **0** paid calls · next: Try On Person. |
| 2026-11-01 | **#135 Create My Croquis house-style mannequin v4 DEPLOYED:** tip  /  · prompt croquis-lineart-v4 · style ref female-straight · no garment rendering · BE 42 mocked · **0** paid calls. |
| 2026-11-01 | **#135 Create My Croquis P0 TypeError hotfix DEPLOYED:** tip  /  · SDK unexpected keyword  caused false recon at 17:02Z · fix  + lease≥timeout+120 + prompt v3 + FE poll · held reservation released $0 · mocked BE 42 / FE 7 · **0** paid calls. |
| 2026-11-01 | **#135 Create My Croquis DEPLOYED — READY FOR OWNER TEST:** tip `623ef821` · FE+BE+worker · Alembic **014** · MY_CROQUIS UI/upload/AI/LIVE_HTTP ON · budget $5/$1/$5/100¢ + 5 gens/day · nginx personal-croquis allowlist · backup `croquis-prod-deploy-20261101T123132Z` · no-bill smoke re-verified PASS (upload+erase) · owner Generate only · drafts #141/#142 unmerged. |
| 2026-10-29 | **Issue #128 / PR #130 Magic source provenance:** generation-boundary look/front/back IDs on paid artifacts (bind + skip paths); mid-run Magic swap keeps original provenance / newer draft source / unbound artwork / cost / one provider call; HEAD `c16acf41` / impl `0561bb56` / blob `e04fdbcf`; Ruff 9 / mypy 51; production FE `bfbdd03f-decimal` / BE `311e259a` **unchanged**; **0 paid AI**; **STOP for Technical PM final acceptance — do not deploy**. |
| 2026-10-29 | **Issue #128 / PR #130 structural & visual identity:** authorized-snapshot artifact retention on piece-list drift; `color_treatment`/`visible_details` identity fingerprint; tip `991244fa727bf01a6aed15bf7471dae776239d62` / commit `4cb7d8f05a18ba47eea5c3c35b6f839f1d3cad35` / blob `2b684a28f257c3824a05405e3f75f54c0877edb9`; 12 focused / 114 broader pass / 1 baseline async_worker fail; Ruff 9 / mypy 51; production FE `bfbdd03f-decimal` / BE `311e259a` **unchanged**; **0 paid AI**; **STOP for Technical PM re-review — do not deploy**. |
| 2026-10-29 | **Issue #128 / PR #130 data-integrity closure:** garment-identity fingerprint fail-closed skip; PDF-assembly revision/meas/identity/dirty CAS; independent SQLAlchemy session concurrency tests; tip `44afea60f87cec2da59a8710c583c2e84314a5ae` / code `0e341c10e28998c84235c307414f7e0bb4a1c641`; verification 111 pass / 1 pre-existing async_worker fail on baseline `311e259a`; Ruff 9 / mypy 51 parity; production FE `bfbdd03f-decimal` / BE `311e259a` / Alembic `011` **unchanged**; **0 paid AI**; **#125 / #129 independent**; **STOP for Technical PM re-review — do not deploy**. |
| 2026-10-29 | **Issue #128 concurrent-write closure (PARTIAL PASS follow-up):** generation-boundary capture + post-provider `FOR UPDATE` re-read; live-spec enrich on mid-run measurement edits; skip draft.spec when pack ownership moved (PDF-only); retain artifacts/cost; never re-call paid AI; mocked DB persist/GET tests; enrich tip `6ac13dc3` retained; production FE `bfbdd03f-decimal` / BE `311e259a` / Alembic `011` **unchanged**; **0 paid AI**; **STOP for Technical PM re-review — do not deploy**. |
| 2026-10-28 | **PR #123 review-guard closure:** fail-closed non-Professional stage + current `last_run_id` + outfit-referenced artifact checks; legacy blank stage only with Professional draft evidence; **69** backend regressions PASS; production FE `13b26c3a-apifix` / BE `005034d5` / Alembic `011` **unchanged**; **0 paid AI**; **STOP for Technical PM — do not deploy**. Issue #124 (FE decimals + FR-B9F9 fidelity) tracked separately. |
| 2026-10-28 | **PR #123 clean replacement for #122 (CHANGES REQUIRED closure)** @ `80e86f90`/`43c8d376`: review→PDF invalidation + fingerprint review tokens; auth-derived reviewer; sanitized fixtures; private FR-3958 evidence kept off git; production unchanged; superseded tip by review-guard closure above. |
| 2026-10-28 | **PR #118 readiness-gate closure:** reject empty/malformed/duplicate/unconfirmed outfit identities; separate `source=designer` provenance from explicit review confirmation; narrow measurement exceptions (code/pom/value/revision + rationale; no blanket); mypy clean on manufacturing module; regressions added; prior 14-page private visual QA retained; production unchanged; **0 paid AI**; **STOP for PM acceptance — no deploy**. |
| 2026-10-28 | **PR #118 PM amendment (CHANGES REQUIRED):** fail-closed SAMPLE-READY gates; conservative unverified detail art (no pixel trust); `_SizedImage` immutable wrap + BOM color-list normalization + dedicated detail pages; negative trousers/hoodie + positive complete + unmarked wrong-garment tests; private FR-3958 Magic+6-artifact visual QA (14 pages); production FE `69b83c01` / BE+worker `7af9c809` / Alembic `011` unchanged; **0 paid AI**; Technical PM CONDITIONAL PASS + HOLD for readiness-gate closure. |
| 2026-10-28 | **Manufacturing-ready Sample-Development Tech Pack foundation** draft PR #118 @ `bfaf4651`: readiness levels, POM contradiction flags, artifact exclusion, offline FR-3958 preview; production unchanged; **0 paid AI**; Technical PM returned **CHANGES REQUIRED** (see amendment row above). |
| 2026-10-27 | **Professional AI Technical Pack quality audit (docs only):** inspected real PDFs FR-7182 / FR-D47D / FR-CF5A vs Magic Looks; FR-3958 NOT EVALUABLE; offline pytest **20 passed**; decision **NEEDS IMPROVEMENT** (P0 multi-piece collapse + `approved_template` overclaim); deliverable `docs/TECHPACK-PROFESSIONAL-QUALITY-AUDIT.md`; FE/BE/worker/Alembic **unchanged**; **0 paid AI**; **STOP for PM** — no fix/deploy. |
| 2026-10-27 | **OWNER ACCEPTANCE PASS — Measurements & Details** on FE `69b83c01` (PR #114): idle editor, Done save, reopen persistence, Generate-not-stale-Download after edit with existing Professional PDF. Production lineage preserved (`732bda9f` / worker / Alembic `011`). |
| 2026-10-27 | **PR #114 Done/save race FE LIVE** @ `69b83c01` (quiet autosave + PDF validity retained); BE `732bda9f` unchanged; **0 paid AI**. |
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
