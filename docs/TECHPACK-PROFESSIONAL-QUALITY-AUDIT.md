# FashionRise — Professional AI Technical Pack Quality Audit

**Date:** 2026-10-27 (Asia/Jerusalem)  
**Auditor role:** Senior product / technical fashion-quality review (evidence only)  
**Scope:** Existing Professional AI Technical Packs on production lineage — **no** paid OpenAI/image calls, **no** production code/deploy/migration changes  
**Production lineage preserved:** FE `69b83c01` (PR #114) · BE `732bda9f` · Alembic `011` · AI worker unchanged  
**Owner acceptance (Measurements & Details):** **PASS — 2026-10-27** (recorded in `docs/00-PROJECT-STATUS.md`)  
**Cursor paid AI spend this audit:** **$0**

**Decision: NEEDS IMPROVEMENT**

Single-garment packs with distinctive, front-visible features can be useful **drafts for patternmaker review**. They are **not** production-validated manufacturing tech packs. Multi-piece outfits currently fail garment-identity fidelity. Several honesty/labeling defects remain in shipped PDFs.

---

## 1. Executive quality assessment

| Question | Verdict |
|---|---|
| Are existing Professional packs genuinely useful? | **Conditionally yes** for clear one-piece looks (e.g. FR-7182 pink striped mini) as **UNVERIFIED drafts**. |
| Source-faithful? | **Mixed.** Front flats for distinctive one-pieces track Magic Looks well. Multi-piece FR-D47D **omits trousers** and labels the pack as a single dress. |
| Professionally presented? | **Mostly.** Cover, DRAFT/UNVERIFIED banners, NOT TO SCALE pattern warnings, and PROPOSED BACK labels are present on V3.1 exports. Layout still squeezes some detail art; older V2 export (FR-CF5A) lacks V3.1 material REVIEW treatment. |
| Safe to treat as manufacturing-ready? | **No.** Explicit draft/unverified posture is correct; pattern inventory still over-labels AI pieces as `approved_template`. |

**Overall:** Stop for PM review of this evidence. Recommended next step is a **targeted multi-piece + honesty fix**, then owner visual review of a regenerated single-piece pack — **not** a broad redesign and **not** a paid re-generate wave until PM approves.

---

## 2. Inventory — real vs simulated artifacts

### 2.1 Production Professional exports inspected (real)

| Style | Export id (prefix) | Pages | Bytes | Generated (UTC) | Footer brand | Magic Look | AI flats stored |
|---|---|---|---|---|---|---|---|
| **FR-7182** Pink Dress | `f91e0a52…` | 7 | ~9.5 MB | 2026-10-27 09:42 | Create Real Design **V3.1** | Yes (`7182a20e…`) | flat_front, flat_back_proposed, detail_callouts, pattern_sheet |
| **FR-D47D** Black tunic + trousers (source) | `cffdfb8a…` | 7 | ~7.6 MB | 2026-10-27 10:42 | **V3.1** | Yes (`d47ddf1b…`) | Same four kinds, but **only for one synthetic piece** |
| **FR-CF5A** Burgundy slip | `ddffdd46…` | 7 | ~8.5 MB | 2026-10-26 22:55 | Create Real Design **V2** | Yes (`cf5adf97…`) | flat_front, detail_callouts, pattern_sheet (**no** flat_back_proposed artifact) |

Storage root (private, not copied into git): `/var/lib/fashionrise/storage/private_techpacks/…`  
Magic Looks: `/var/lib/fashionrise/storage/uploads/ai/<look_id>_….png`  
Local private working copies used for this audit lived only under `/tmp/fr-audit-private/` (chmod 700) and were **not** committed.

### 2.2 Candidate case that is **not** evaluable as Professional output

| Style | What exists | Professional PDF? | Visual fidelity |
|---|---|---|---|
| **FR-3958** Lavender zip hoodie + yellow shorts | Draft with 2 outfit pieces; look notes match the described outfit | **No exports, no professional runs** | **NOT EVALUABLE** — no Professional PDF or AI flats |

### 2.3 Simulated / offline-only (not treated as visual fidelity proof)

| Artifact class | Role in this audit |
|---|---|
| `MockProfessionalProvider` + pytest fixtures | Structural/provenance/PDF-text checks only |
| Fixture PNGs / synthetic pink blocks in tests | Confirm pipeline wiring, **not** source fidelity |
| Extracted PDF text alone | Used as supporting evidence; **visual** page renders + Magic/flat PNGs required for PASS on silhouette/color/flats |

### 2.4 What was **not** done

- No new OpenAI / image-generation provider calls  
- No Professional PDF regeneration  
- No production code, deploy, migration, DB reset, Cloudflare, or worker changes  
- No private customer PDFs/images attached to the GitHub PR  

---

## 3. Case-by-case fidelity scorecards

Severity key: **P0** misleading/materially wrong · **P1** major fidelity/functional defect · **P2** polish · **P3** optional.

### Case A — FR-7182 (pink diagonal-stripe mini dress) — **evaluable**

**Source:** Magic Look front croquis — hot-pink/white wide diagonal stripes, deep plunging V to waist, long fitted sleeves, bodycon mini.  
**PDF:** 7 pages; cover Magic Look; component flats + details; measurements; pattern schematics; construction; readiness checklist.

| Dimension | Result | Evidence | Severity |
|---|---|---|---|
| Garment identity | **PASS** | Cover + p3: one `ONE_PIECE: Pink Dress`; matches Magic | — |
| Silhouette | **PASS** | Front flat bodycon mini with defined waist; matches Magic proportions | — |
| Neckline / sleeves | **PASS** | Deep V to waist + long fitted sleeves on Magic, analysis text, and front flat (p3) | — |
| Color / textile fidelity | **PASS** (with caveat) | Hot pink / white diagonal stripes preserved on flats; shell name `other` + `100% cotton` is designer/estimate — not visually confirmed stretch/jersey, but not a silk≠cotton contradiction | P3 caveats |
| Front technical flat | **PASS** | Front flat readable; stripe direction and plunge preserved | — |
| Back-view honesty | **PASS** | `PROPOSED BACK — UNVERIFIED` label present (p3); no back Magic | — |
| Measurements / provenance | **PASS** (partial empties) | Body (p2) designer-sourced; finished POMs (p4) mix designer values + Empty neckline/hem — Empty clearly marked | P2 empty POMs |
| Materials / construction | **PASS** with honesty gap | Pull-on closure; BOM estimates labeled Estimate; construction steps Estimate (p6) | P2 |
| Readability / layout | **PASS** / **P2** | Flats large enough on p3; detail_callouts sheet present; pattern grid labels small (p5) | P2 |
| Professional usefulness | **PASS as draft** | Useful patternmaker-review pack for this distinctive dress; **not** manufacturing-validated | — |

**Extra finding (P1):** Pattern inventory rows for AI-sourced pieces (including back pieces whose notes say back is not shown) display Review = `approved_template` (p5 / draft `pattern_pieces[].review_state`). Default comes from `techpack_compatibility.py` (`review_state or "approved_template"`). That overstates verification.

---

### Case B — FR-D47D (black V-slit tunic + cream trousers) — **evaluable; FAIL identity**

**Source Magic Look:** Clearly **two garments** — matte black three-quarter-sleeve tunic with shallow V-slit round neck + cream slim full-length trousers.  
**Draft after later structure repair:** `Top` + `Trousers` (2 pieces).  
**Professional export / PDF:** `piece_count: 1`, cover **“DRESS: Garment”**, analysis on synthetic `piece-1`, **trousers absent** from components/measurements/BOM/pattern.

| Dimension | Result | Evidence | Severity |
|---|---|---|---|
| Garment identity | **FAIL** | Magic = 2 pieces; PDF p1 `Outfit pieces: 1` / `DRESS: Garment`; only tunic flats; trousers omitted | **P0** |
| Silhouette | **FAIL** (pack) / tunic flat OK | Tunic flat roughly matches top; cream trousers never illustrated as a component | **P0** |
| Neckline / sleeves | **PASS** (tunic only) | V-slit + 3/4 sleeves match Magic on front flat (p3) | — |
| Color / textile fidelity | **FAIL** (outfit) | Trousers colorway `#F5F0E6` present in draft identity but missing from PDF materials; tunic black OK | **P1** |
| Front technical flat | **PASS** (tunic) / **FAIL** (outfit) | Tunic front flat source-faithful; no trouser flat | **P0** |
| Back-view honesty | **PASS** (tunic) | `PROPOSED BACK — UNVERIFIED` on p3 | — |
| Measurements / provenance | **FAIL** | p4: sleeve length 62 cm with note “Standard **long-sleeve** assumption” while Magic/analysis are **three-quarter**; many Empty POMs; category oscillates dress/shirt | **P1** |
| Materials / construction | **FAIL** | Empty shell on draft pieces; PDF BOM invents collar/placket/buttons/zipper TBD for a simple V-slit pull tunic; trousers BOM absent | **P1** |
| Readability / layout | **PASS** / **P2** | Structure readable; detail thumbnails dark/small (p3) | P2 |
| Professional usefulness | **FAIL** | Misleading as a complete outfit pack; would send wrong BOM/POM set to a maker | **P0** |

**Root-cause notes (code / data, no fix applied):**

1. At generate time the run recorded `pieces_total: 1` / `piece_count: 1` with analysis id `piece-1` — PDF built as a single dress before later `get_draft` structure repair split the outfit to Top+Trousers (`techpack_service.get_draft` → `repair_outfit_from_evidence`).  
2. Pipeline itself iterates all passed pieces (`run_professional_pipeline` in `techpack_ai_professional.py`); the failure mode here is **wrong/incomplete piece list at paid generate time**, plus **no regeneration** after repair.  
3. Persist fallback maps unknown piece ids onto `pieces[0]` (`techpack_ai._persist_professional_result`), which can attach arts to the wrong piece if IDs drift.

---

### Case C — FR-CF5A (burgundy asymmetric slip) — **evaluable**

**Source:** Burgundy satin-sheen slip, cowl neck, spaghetti straps, dramatic asymmetric pointed hem.  
**PDF:** V2 footer; Professional arts without proposed-back artifact; page 3 shows category schematic back.

| Dimension | Result | Evidence | Severity |
|---|---|---|---|
| Garment identity | **PASS** | One dress; matches Magic | — |
| Silhouette | **PASS** | Slim slip + asymmetric high-low point preserved on front flat / detail sheet (p3–p4) | — |
| Neckline / sleeves | **PASS** (visual) / **FAIL** (POM) | Cowl + spaghetti straps correct visually; **Sleeve length 60 cm Designer** on sleeveless dress (p5) | **P1** |
| Color / textile fidelity | **FAIL** (claims) | Visual sheen matches silk/satin; materials table **Shell: silk** + **Composition: 100% cotton** (p3) with **no REVIEW banner** on this V2-era PDF | **P1** |
| Front technical flat | **PASS** with style note | Front art matches distinctive hem/cowl/color; leans toward rendered fashion flat vs stark CAD line flat | P2 style |
| Back-view honesty | **PASS** (flat page) / **P2** (details) | p3: `BACK — category schematic (no AI back)` honest; detail sheet (p4) still draws a full back fashion view inside callout collage — weaker separation than PROPOSED BACK label | P2 |
| Measurements / provenance | **FAIL** | Sleeveless garment carries sleeve length 60; hem/armhole/neckline Empty | **P1** |
| Materials / construction | **FAIL** on contradiction surfacing | silk≠cotton present; V3.1 code path would emit `REVIEW:` (`techpack_pdf.py` + `material_contradiction`) but **this stored PDF does not** | **P1** |
| Readability / layout | **PASS** | Detail sheet (p4) is the strongest layout of the three; p3 schematic back is clear | — |
| Professional usefulness | **NEEDS IMPROVEMENT** | Visually recognizable slip draft, but material contradiction + sleeveless sleeve POM undermine trust | **P1** |

---

### Case D — FR-3958 (lavender hoodie + yellow shorts) — **NOT EVALUABLE**

Draft + look notes exist; **zero** Professional exports/runs/artifacts. No visual fidelity score possible without inventing paid output.

---

## 4. PDF layout findings (cross-cutting)

| Topic | Observation |
|---|---|
| Cover / Magic Look | Real Magic image on cover (p1) for all three; look notes present |
| Hierarchy / typography | Clear DRAFT/UNVERIFIED header band; component H1/H3 structure usable |
| Technical flat size | Front/back flats on V3.1 packs are large enough to judge silhouette (p3) |
| Detail callouts | Full detail sheets exist as artifacts; on FR-7182/D47D component pages they compete with flats and can read small; FR-CF5A effectively gets a dedicated detail page (p4) |
| Measurement tables | Sources shown (Designer / Calculated / Empty / Estimate) — good provenance UX when values are honest |
| BOM | Largely Estimate/TBD; acceptable for draft **if** not contradicted by wrong garment set |
| Pattern inventory | Schematics correctly disclaimer’d NOT TO SCALE; **Review column over-claims** `approved_template` for AI rows |
| Page breaks / whitespace | FR-CF5A p3 ends with “Garment detail illustrations” heading then continues on p4 — awkward split; FR-D47D construction spills p5→p6 |
| Warnings / provenance | Footer generation mode + paid sections listed; status DRAFT/UNVERIFIED consistent |
| Schematic vs cut patterns | Copy correctly states planning illustrations, not production-validated cuts |

**Draft vs manufacturing:** All inspected packs are **drafts suitable for patternmaker review only**. None should be treated as production-validated manufacturing tech packs.

---

## 5. Prioritized findings (P0 / P1 / P2)

### P0

1. **Multi-piece outfit collapsed / trousers omitted (FR-D47D)**  
   - Evidence: Magic Look two garments; PDF `Outfit pieces: 1`, `DRESS: Garment`; AI run `piece_count=1`; artifacts only under `piece-1`.  
   - Impact: Maker receives a false single-garment pack.  
   - Code loci to inspect for fix (not changed this audit):  
     - `backend/app/services/techpack_ai_professional.py` (`run_professional_pipeline` piece loop)  
     - `backend/app/services/techpack_ai.py` (`_persist_professional_result` fallback to `pieces[0]`)  
     - `backend/app/services/techpack_service.py` (`get_draft` / `repair_outfit_from_evidence` timing vs generate)  
     - `backend/app/services/techpack_pdf.py` (renders whatever outfit.pieces exist at export)

2. **Pattern inventory Review=`approved_template` for AI / unverified back pieces (FR-7182 p5)**  
   - Evidence: draft `source: ai` + notes “Back view is not shown” yet `review_state: approved_template`.  
   - Code: `backend/app/services/techpack_compatibility.py` (~line 200) defaults missing review_state to `approved_template`.

### P1

3. **Material name vs composition contradiction not flagged on stored FR-CF5A PDF** (silk + 100% cotton, p3). Current V3.1 PDF builder has `REVIEW:` via `material_contradiction`, but this export is V2-branded and predates/omits that banner.  
4. **Sleeveless dress carries Sleeve length 60 cm** (FR-CF5A p5) despite analysis “Sleeveless with narrow spaghetti straps”. Compatibility warnings exist in tests (`measurement_garment_mismatch`) but did not prevent the shipped PDF table from showing the value as Designer.  
5. **FR-D47D sleeve POM assumes long sleeve** while Magic/analysis are three-quarter (p4 note).  
6. **FR-D47D BOM proposes collar/placket/buttons/zipper** for a minimal V-slit tunic with empty closure — invented hardware path.  
7. **Post-repair draft ≠ exported PDF** for FR-D47D: editor can show Top+Trousers while Download still serves the one-piece Professional PDF until a new paid generate — high user confusion risk (related to dirty/generate UX already hardened on FE `69b83c01`, but historical PDF remains wrong).

### P2

8. Detail illustration crowding / small labels on pattern grids.  
9. FR-CF5A detail collage includes a full back fashion view while component back is only a schematic — messaging inconsistency.  
10. Generic Estimate construction steps still mention “Set sleeves” language on some paths (V3.1 filters exist in tests; older PDFs vary).  
11. FR-7182 shell `other` / cotton not visually confirmed — acceptable if clearly estimate, but weak for “professional” materials identity.

### P3

12. Stronger grainline / stripe-matching callouts for diagonal prints.  
13. Optional second Professional case (FR-3958) once multi-piece fix lands.

---

## 6. Automated test coverage (offline)

**Command (local disposable DB `fashionrise_test`, mock provider, $0):**

```text
pytest tests/test_techpack_v3_professional.py \
       tests/test_techpack_v31_one_tap.py \
       tests/test_techpack_v2_pdf_fixtures.py \
       tests/test_techpack_provenance.py -q
```

**Result: 20 passed** (2026-10-27 audit run).

| Area | What tests actually prove | Gap vs visual fidelity |
|---|---|---|
| Mock professional pipeline | Artifacts kinds, cost cents > 0, owner isolation | Mock PNGs ≠ Magic fidelity |
| One-tap / idempotency / progress | Queue settle, replay same run_id | No image QA |
| Material contradiction helper | `silk` vs `100% cotton` → message; PDF fixture may contain REVIEW | Does not re-check **stored production** PDFs |
| Sleeveless construction / inventory | Filters “set sleeves”; sleeve cut_qty null in helper unit tests | Does not fail export when designer sleeve_length=60 remains |
| Two-piece PDF fixture | Separate shirt/trouser sections in **offline fixture** PDF | Did **not** catch FR-D47D production collapse (fixture assumes correct piece list) |
| Provenance helpers | Professional claim requires artifacts | No pixel compare |
| NOT TO SCALE / missing back copy | String presence in fixture PDFs | Structural only |

**Do not treat green pytest as proof that production AI flats match Magic Looks.**

---

## 7. Important remaining unknowns

1. Exact outfit.pieces JSON **at the moment** FR-D47D paid generate started (pre-repair) — only post-repair draft + run metadata (`piece_count=1`, `piece-1`) were available.  
2. Whether any family-beta user besides these three has additional Professional PDFs not under the scanned storage tree (scan found **3** professional exports total).  
3. FR-3958 Professional quality once generated.  
4. Back-view quality when a real Dual Magic back job exists (all three audited packs had `back_image_present: false`).  
5. Whether regenerating FR-CF5A on current V3.1 code alone clears REVIEW/sleeve issues without further code changes.

---

## 8. Recommended minimal fixes (by user impact)

1. **P0 — Multi-piece generate/export gate:** Refuse or split Professional generate unless `outfit.pieces` count matches Magic evidence / detection; never export a Professional PDF that drops sibling garments; after structure repair, mark `dirty_since_generation` and hide Download (FE already partly does this — ensure repair path sets dirty).  
2. **P0 — Stop defaulting AI pattern rows to `approved_template`:** Default AI / inferred / unseen-back rows to `proposed_unverified` in `techpack_compatibility.py`.  
3. **P1 — Harden materials + sleeveless POMs at PDF time:** Always emit REVIEW for name/composition clashes; suppress or flag sleeve length when analysis is sleeveless (even if designer value present).  
4. **P1 — Re-audit after fix:** Owner visual review of **one** regenerated single-piece (FR-7182 or FR-CF5A) and **one** multi-piece (FR-D47D or FR-3958) — paid calls only with explicit owner authorization.

---

## 9. Decision

### **NEEDS IMPROVEMENT**

- **Acceptable as-is only for:** distinctive **single-garment** drafts when the user understands DRAFT/UNVERIFIED + patternmaker review (FR-7182 is the strongest existing example).  
- **Not acceptable as-is for:** multi-piece outfits (FR-D47D), or any claim of manufacturing-validated packs.  
- **Insufficient evidence for:** lavender hoodie case (FR-3958) and any back-from-Magic fidelity.

**Next step for PM:** Approve a **targeted honesty + multi-piece fix** (docs/code), then authorize a bounded paid visual re-check — **or** request owner visual review of FR-7182 pages 1/3/5 first if product priority is single-dress quality.

---

## Appendix — Production lineage snapshot (audit time)

| Layer | Value |
|---|---|
| Frontend | `69b83c010391cb14d937a0ba777a77a8de87be73` (`version.json` / Nginx `current`) |
| Backend | `732bda9f` (service files hash-matched to that commit for `techpack_pdf.py` / `techpack_ai_professional.py`) |
| Alembic | `011` |
| Worker | Unchanged (`gpt-6-luna` / image `gpt-image-2.5-sunburst` on completed runs) |
| Paid calls this audit | **0** |
