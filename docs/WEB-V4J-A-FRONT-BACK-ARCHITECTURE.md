# WEB-V4J-A — Front/Back croquis architecture & persistence audit

**Issue:** [#42](https://github.com/perielad2-netizen/FashionRise/issues/42)  
**Phase:** Architecture / artwork briefing only — **no production asset changes**, **no paid AI**, **no merge/deploy**.  
**Base:** `main` @ `dfcaa609` (WEB-V4I FE deployed). Backend/worker remain `2cbc1ad0` · Alembic `005`.

---

## 1. Goals (product)

- Every selectable built-in model (6F + 4M) eventually gains an **approved anatomically plausible rear companion**.
- Studio exposes an obvious **Front / Back** control; default **Front**.
- Front and back garment artwork (strokes, fills, materials) are **independently editable** and must not overwrite each other when switching sides.
- Legacy drafts/saved designs reopen with **identical** front model IDs, geometry, strokes and fills.
- Magic, when later authorized, acts on the **active side only**.

---

## 2. Asset inventory (current production)

| Kind | Location | Count | Notes |
|------|----------|------:|-------|
| Selectable canvas fronts | `web-ui/public/models/library/<id>.png` | 10 | IDs in `modelLibrary.ts` |
| Card thumbs | `web-ui/public/assets/ui/models/library/<id>_card.png` | 10 | Picker only |
| Legacy fronts | `female_model.png`, `male_model_display.png` | 2 | Pre-V4D IDs `female` / `male` — **never remap** |
| Utility | custom upload / blank | — | **No rear** in V4J |

**Rear companions today:** **none**. Do not ship mirrored fronts.

**Operator front masters (this pack):** preserved under `docs/web-v4j-a/front-refs/` after ID matching. These are **source-of-truth for rear briefing**, not replacements for shipped library files in this phase. Eight masters are higher-resolution (1086×1448) than shipped 900×1200; two (`female-straight`, `female-hand-hip`) share 656×1199 canvas size with the library (identical silhouette IoU 1.0, different file bytes).

---

## 3. Model ID matching (uploads → library)

Matching used alpha-cropped silhouette IoU + average-hash Hamming distance against shipped library PNGs. Upload order was ignored.

| `modelId` | Pose label | Upload (original name) | Ref size | Lib size | Silhouette IoU |
|-----------|------------|------------------------|----------|----------|----------------|
| `female-straight` | Standing | `80f8e22f-…png` | 656×1199 | 656×1199 | 1.000 |
| `female-hand-hip` | Hand on hip | `46294290-…png` | 656×1199 | 656×1199 | 1.000 |
| `female-contrapposto` | Contrapposto | `97d36898-…png` | 1086×1448 | 900×1200 | 0.990 |
| `female-cross-ankle` | Crossed ankles | `ff660483-…png` | 1086×1448 | 900×1200 | 0.990 |
| `female-atelier` | Atelier | `44f151fe-…png` | 1086×1448 | 900×1200 | 0.988 |
| `female-cross-leg` | Crossed leg | `80663d57-…png` | 1086×1448 | 900×1200 | 0.988 |
| `male-straight` | Standing | `d02c0b5e-…png` | 1086×1448 | 900×1200 | 0.988 |
| `male-step` | Step | `118c5f39-…png` | 1086×1448 | 900×1200 | 0.981 |
| `male-walk` | Walk | `1ef9f89e-…png` | 1086×1448 | 900×1200 | 0.989 |
| `male-contrapposto` | Contrapposto | `32fc6040-…png` | 1086×1448 | 900×1200 | 0.992 |

Full metrics: `docs/web-v4j-a/front-ref-match-report.json`.

**Constraint for rear generation:** output PNG must target the **same pixel canvas as the shipped library front** for that ID (656×1199 or 900×1200), transparent background, figure scale/vertical placement matching the front content bbox when both are normalized to that canvas. Masters at 1086×1448 are briefing references only unless a later asset PR deliberately reships higher-res fronts (out of scope for V4J-A).

---

## 4. Document model (backward compatible)

### 4.1 Current schema (must keep loading)

`fashionrise.studio.draft.v1` (`StudioDraftDocument` in `web-ui/src/lib/draftDocument.ts`):

- `strokes[]`, optional `fills[]`
- `model: ModelChoice` (includes legacy `female`/`male`)
- brush, dimmed, `clientRevision`, `updatedAt`, custom reference fields

Saved designs embed the same draft document shape.

### 4.2 Recommended additive shape (no forced schema rename)

Keep `schema: "fashionrise.studio.draft.v1"`. Add **optional** fields only:

```ts
type GarmentSide = 'front' | 'back'

type StudioDraftDocumentV4J = StudioDraftDocument & {
  /** Which side the editor is showing. Default / missing => 'front'. */
  activeSide?: GarmentSide
  /**
   * Back-side artwork. Absent => design is front-only (all legacy docs).
   * Never auto-create on load.
   */
  back?: {
    strokes: Stroke[]
    fills: FillOp[]
  }
}
```

**Compatibility rules:**

1. **Read path:** If `back` absent → behave exactly as today; `activeSide` forced to `front`.  
2. **Write path:** Top-level `strokes` / `fills` remain the **front** side always (legacy readers keep working).  
3. **Fingerprint / OCC:** Include `activeSide` + `back` in `draftContentFingerprint` when present so conflicts detect back edits.  
4. **No DB migration** required — JSON document blob stays schemaless at the API.  
5. **Never** invent `back` for legacy reopen; never copy front strokes into `back` on load.  
6. **Model switch:** Changing `model` keeps front artwork (existing confirm dialog); clear or confirm-clear `back` if the new model has no approved rear (or keep orphaned back disabled in UI until a rear exists — product choice for V4J-B; recommend **disable Back** rather than deleting silently).

### 4.3 Rejected alternatives (for this product)

| Idea | Why not |
|------|---------|
| Flip/mirror front PNG as rear | Explicitly forbidden by Issue #42 / operator |
| Separate design rows per side | Splits one garment; breaks My Designs mental model |
| New schema `draft.v2` required for all saves | Forces migration of every client; unnecessary if additive fields parse safely |
| Remap legacy `female`/`male` onto new IDs | Geometry drift / data loss |

---

## 5. Library / runtime wiring (later implementation — not this PR)

```ts
// Conceptual extension — do not ship until rears approved
type BuiltinModelDef = {
  // ...existing fields
  rearCanvasSrc?: string // e.g. '/models/library/<id>-back.png'
}
```

- `canvasSrcForModel(id, side)` returns front today; rear only when `rearCanvasSrc` set.  
- Custom / blank / legacy without rear: Back control **disabled** with honest copy.  
- Design paper stays **768×1024**; croquis still letterboxed inside paper as today.

---

## 6. Editor / undo / autosave ownership

| Concern | Proposal |
|---------|----------|
| Undo stacks | Per-side stacks **or** single stack with side-tagged entries; switching sides must not pop the other side’s history. Prefer **side-tagged single history** so one Undo bar remains. |
| Autosave | Persist both sides in one draft document; status label unchanged. |
| Conflict dialog | Fingerprint includes both sides; Keep device / Use cloud stays document-level. |
| Immersive / zoom | Side toggle available in normal Studio and immersive toolbar; viewport transform shared. |
| Dim reference | Applies to the active side’s croquis. |

---

## 7. Export & Magic boundaries

- **Export default:** active side PNG (current behavior = front).  
- **Optional later:** “Export both” → two files or labeled combined sheet (V4J-C).  
- **Magic:** only authorized active side; never send the inactive side; no paid calls in V4J-A.  
- **Pose fidelity (PR #41):** remains undeployed; V4J-A does not touch worker prompts.

---

## 8. Data-loss protection checklist

- [x] Legacy model IDs still resolve to original geometry paths.  
- [x] Additive JSON fields only; old clients ignore `back` / `activeSide`.  
- [x] Front strokes/fills stay at top-level keys.  
- [x] No production library PNG replacement in this PR.  
- [x] No mirrored rear proposed as shippable asset.  
- [ ] Operator approves generated rears before any FE asset PR.  
- [ ] Implementation PR adds parser tests: legacy doc round-trip bitwise-equal on front fields; doc with `back` round-trips; missing `back` does not synthesize strokes.

---

## 9. Delivery phases

| Phase | Scope | Status |
|-------|--------|--------|
| **WEB-V4J-A** (this) | Match fronts, preserve masters, rear artwork specs, persistence audit, docs | **Draft PR — STOP for PM** |
| **Artwork gate** | ChatGPT/operator produces rears from specs; operator accepts | Pending |
| **WEB-V4J-B** | Ship approved `-back.png`, library fields, Front/Back UI, side-aware undo/save | Not started |
| **WEB-V4J-C** | Dual export / polish | Not started |

---

## 10. Out of scope / safety

- No backend, worker, Alembic, Nginx, or Cloudflare changes.  
- No paid OpenAI calls.  
- No production deploy.  
- No Issue #42 implementation UI in this PR.  
- Do not auto-merge docs PRs #44 / #46 / #49.
