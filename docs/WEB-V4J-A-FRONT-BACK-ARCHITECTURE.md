# WEB-V4J-A — Front/Back croquis architecture & persistence audit

**Issue:** [#42](https://github.com/perielad2-netizen/FashionRise/issues/42) (**OPEN**)  
**Replacement PR:** clean docs-only branch from GitHub `main` @ `c6fc1eb8` (supersedes content of draft PR [#50](https://github.com/perielad2-netizen/FashionRise/pull/50); **do not close #50** until PM accepts this pack).  
**Phase:** Architecture / artwork briefing only — **no production code**, **no paid AI**, **no merge/deploy**, **no rear PNG generation**.  
**Production baseline (2026-10-25, operator-accepted):** FE combined release **`a740a9b7`** · BE/worker maint tip **`12f7acdf…`** · Alembic **`005`** · Sunburst high.  
**Closed gates that unblock resume:** Issues [#51](https://github.com/perielad2-netizen/FashionRise/issues/51), [#59](https://github.com/perielad2-netizen/FashionRise/issues/59), [#60](https://github.com/perielad2-netizen/FashionRise/issues/60), [#64](https://github.com/perielad2-netizen/FashionRise/issues/64), [#39](https://github.com/perielad2-netizen/FashionRise/issues/39).  
**Retain:** Verified design decisions from PR #50 tip `34e6d0d1` (schema v2 + BE downgrade guards + matching manifest). Ten front models matched; each still requires a real rear companion.

**Public-history constraint:** Do not merge or cherry-pick PR #50 commits that introduced front-master PNGs (`165865d8`). Tip deletion does not remove those blobs from that branch’s ancestry. This pack copies sanitized docs only onto a new `main`-rooted branch.

---

## 1. Goals (product)

- Every selectable built-in model (6F + 4M) eventually gains an **approved anatomically plausible rear companion**.
- Studio exposes an obvious **Front / Back** control; default **Front**.
- Front and back garment artwork (strokes, fills, materials) are **independently editable** and must not overwrite each other when switching sides.
- Legacy drafts/saved designs reopen with **identical** front model IDs, geometry, strokes and fills.
- Magic, when later authorized, acts on the **active side only**.
- **Older clients must never silently delete Back artwork** during save, restore, conflict, or retry.

---

## 2. Asset inventory (current production)

| Kind | Location | Count | Notes |
|------|----------|------:|-------|
| Selectable canvas fronts | `web-ui/public/models/library/<id>.png` | 10 | IDs in `modelLibrary.ts` |
| Card thumbs | `web-ui/public/assets/ui/models/library/<id>_card.png` | 10 | Picker only |
| Legacy fronts | `female_model.png`, `male_model_display.png` | 2 | Pre-V4D IDs `female` / `male` — **never remap** |
| Utility | custom upload / blank | — | **No rear** in V4J |

**Rear companions today:** **none**. Do not ship mirrored fronts. Production model assets must not be altered until Stage C assets are operator-approved.

### 2.1 Operator front masters — provenance (public repo)

This GitHub repository is **PUBLIC**. Operator-supplied front PNG masters were used privately for ID matching. **No redistribution / license attestation** is recorded for publishing those binaries.

**Policy for this clean pack:**

- **Do not publish** the ten original reference PNGs under `docs/web-v4j-a/front-refs/`.
- Retain only the non-sensitive **manifest** `docs/web-v4j-a/front-ref-match-report.json` (dimensions, transparency, content bbox, SHA-256 of the private masters and of shipped library files, IoU metrics) and the rear artwork briefs.
- Masters remain operator-held / offline for ChatGPT briefing until the operator explicitly confirms redistribution rights (or supplies cleared substitutes).
- Do **not** label assets commercially cleared. No generated backs are approved yet.
- Do **not** claim deletion of historically published blobs from GitHub; only ensure this branch’s ancestry never contained them.

Matching table (upload order ignored; silhouette IoU ≥ 0.98):

| `modelId` | Pose label | Ref size | Lib size | Silhouette IoU |
|-----------|------------|----------|----------|----------------|
| `female-straight` | Standing | 656×1199 | 656×1199 | 1.000 |
| `female-hand-hip` | Hand on hip | 656×1199 | 656×1199 | 1.000 |
| `female-contrapposto` | Contrapposto | 1086×1448 | 900×1200 | 0.990 |
| `female-cross-ankle` | Crossed ankles | 1086×1448 | 900×1200 | 0.990 |
| `female-atelier` | Atelier | 1086×1448 | 900×1200 | 0.988 |
| `female-cross-leg` | Crossed leg | 1086×1448 | 900×1200 | 0.988 |
| `male-straight` | Standing | 1086×1448 | 900×1200 | 0.988 |
| `male-step` | Step | 1086×1448 | 900×1200 | 0.981 |
| `male-walk` | Walk | 1086×1448 | 900×1200 | 0.989 |
| `male-contrapposto` | Contrapposto | 1086×1448 | 900×1200 | 0.992 |

Full metrics: `docs/web-v4j-a/front-ref-match-report.json`. IoU / pixel claims are Cursor-reported from the matching run, not independently reprocessed by PM.

**Constraint for rear generation:** output PNG must target the **same pixel canvas as the shipped library front** for that ID (656×1199 or 900×1200). Higher-res private masters are briefing references only.

---

## 3. Why “additive optional `back` on V1” is NOT safe

### 3.1 Current client behavior (today on production FE `a740a9b7` / `main`)

- Working drafts: `fashionrise.studio.draft.v1` via `parseStudioDraftDocument` — rebuilds a **known-field** object (`strokes`, `fills`, `model`, brush, dimmed, revisions). **Unknown keys are dropped** on parse.
- Fingerprint (`draftContentFingerprint`) hashes only front strokes/fills/model/brush/dimmed/custom refs — **not** `back` / `activeSide`.
- Named saves: **separate** envelope `fashionrise.saved_design.v1` with nested `SavedDesignSnapshot` (no draft `schema` / `clientRevision` inside the snapshot). `parseSavedDesignSnapshot` likewise rebuilds known fields only.
- Backend `design_service._studio_content_fingerprint` enumerates the same front-only keys. Create idempotency and OCC “same content” short-circuits use that fingerprint.

### 3.2 Failure mode if we only add optional `back` on V1

1. New client saves a two-sided V1 doc with `back: { strokes, fills }`.
2. Old PWA (still on production FE until upgrade) restores the draft, parses with `parseStudioDraftDocument`, **strips `back`**, and may autosave / conflict-retry / Keep-device.
3. Backend fingerprint (front-only) treats the stripped payload as **identical** to a front-only document if front ink matches → **idempotent no-op or accepted overwrite** that permanently drops Back.
4. Conflict UI may present “equal” fingerprints and auto-accept truncation as intentional.

**Conclusion:** Optional fields the old parser ignores are **not** backward-compatible for a shared mutable working draft. Fail closed.

---

## 4. Chosen document strategy — versioned schema + dual-reader + server reject-on-downgrade

### 4.1 Evaluation summary

| Option | Verdict |
|--------|---------|
| A. Keep `draft.v1` + optional `back`; hope old clients ignore | **Rejected** — old clients rewrite and strip; BE fingerprint cannot see back |
| B. `draft.v2` when two-sided / Front–Back capable; dual-reader on new FE; **server rejects downgrade** | **Chosen** (approved in principle; not implemented) |
| C. Separate DB rows per side | Rejected — splits one garment; breaks My Designs |
| D. Force every client to v2 immediately with a migration job | Unnecessary; front-only v1 remains valid forever |

### 4.2 Working draft schemas

| Schema | Meaning |
|--------|---------|
| `fashionrise.studio.draft.v1` | Front-only working draft (all legacy + any front-only new saves). **No `back` key.** |
| `fashionrise.studio.draft.v2` | Front/Back-capable working draft. Top-level `strokes`/`fills` = **front**. Optional `activeSide`. Optional `back: { strokes, fills }`. |

```ts
type GarmentSide = 'front' | 'back'

type StudioDraftDocumentV2 = {
  schema: 'fashionrise.studio.draft.v2'
  strokes: Stroke[]          // FRONT
  fills: FillOp[]            // FRONT
  activeSide?: GarmentSide   // missing => 'front'
  /**
   * Back artwork bag.
   * - key ABSENT: front-only v2 (allowed briefly during upgrade) — prefer omitting v2 until back exists
   * - key PRESENT with empty arrays: intentional empty back side (user opened Back)
   * These two states MUST fingerprint differently from each other and from v1.
   */
  back?: { strokes: Stroke[]; fills: FillOp[] }
  model: ModelChoice
  // …brush, dimmed, customReference*, clientRevision, updatedAt (same as v1)
}
```

**Normalization rules (FE + BE must agree):**

1. **Absent `back` key** ≠ **`back: { strokes: [], fills: [] }`**. Fingerprint uses a sentinel, e.g. `"back": null` vs `"back": { strokes: [], fills: [] }`.
2. Never invent `back` on legacy reopen. Never copy front ink into `back`.
3. New FE dual-reader: parse v1 and v2; write **v1** while the document is front-only and the Front/Back feature is unused; **upgrade to v2** the first time the user enables Back or any back ink/fill is created; **never downgrade** v2 → v1 on the client.
4. Old FE: continues to parse only v1. A v2 draft is **not** silently opened as empty front — restore must fail closed (show recovery / “update app” / keep server copy), never parse-strip-save.

### 4.3 Server-side downgrade protection (required before any FE enablement)

Backend must treat schema + back bag as part of content identity and write authorization.

**Reject (HTTP 409 Conflict, fail closed)** when any of:

- Stored working draft is `draft.v2` (or has a present `back` key) and the incoming payload is `draft.v1`, or omits `back` while stored has `back`.
- Incoming fingerprint would drop previously present back strokes/fills without an explicit, authenticated “clear back” intent flag (default: **no silent clear**; clearing back requires v2 payload with `back` present and empty/new content under OCC).
- Client capability header/metadata claims `studioSides < 2` while attempting to overwrite a two-sided draft (defense in depth for old PWAs).

**Allow:**

- v1 → v1 front edits (today).
- v1 → v2 upgrade with same front fingerprint + new/empty back (feature onboarding).
- v2 → v2 edits including back-only changes (must change fingerprint).
- Idempotent retries with **byte-equivalent normalized fingerprint** (including back sentinel).

**Never** store partial side data or accept a body that truncates the inactive side.

### 4.4 Rollout order (mandatory)

1. **Backend** fingerprint + reject-on-downgrade + tests (no FE UI yet) — Stage B on **maint BE lineage**.  
2. **Frontend** dual-reader / v2 writer behind a flag; still no Back UI.  
3. Deploy BE → deploy FE readers → then enable Front/Back UI + rear assets (Stage D / WEB-V4J-B).  
4. Old PWAs that never upgrade cannot open v2 drafts for edit; they must not be able to PUT a stripped body successfully.

Feature flag / old-PWA safeguard: Back control hidden until `supportsStudioDraftV2` and server advertises side-aware fingerprint (e.g. `/health` or designs API capability bit). Cached old SW builds remain blocked by server reject even if a buggy client ships.

---

## 5. Required backend changes (explicit)

File today: `backend/app/services/design_service.py` on the **deployed maintenance lineage** (production BE `12f7acdf…` as of 2026-10-25). Do **not** blindly implement or deploy from undeployed `main` / PR #41 pose-packing runtime without a separate maint-aware release plan.

### 5.1 `_studio_content_fingerprint`

Must include (normalized, `sort_keys=True`):

| Field | Normalization |
|-------|----------------|
| `schema` | `draft.v1` / `draft.v2` (and reject unknown for studio drafts) |
| `strokes` / `fills` | Front; missing fills ≡ `[]` (existing rule) |
| `model`, `customReferenceUrl`, `customReferenceKey`, `brush`, `dimmed` | As today |
| `activeSide` | Default `"front"` when absent |
| `back` | Sentinel: JSON `null` if key absent; else `{ strokes, fills }` with fills missing≡`[]` |

Back-only edits **must** change the fingerprint so create-idempotency and OCC “same content” paths cannot no-op them.

### 5.2 Idempotent draft creation (`create_design` studio branch)

Existing behavior: advisory lock → if working draft exists and fingerprints match → return existing; if incoming revision &lt; current → return existing; else conflict.

**Additions:**

- Fingerprint comparison uses §5.1 (includes back).
- If existing is two-sided / v2 and incoming is v1 or stripped → **ConflictError** (`studio_schema_downgrade` / `back_stripped`), never return existing as “success” that hides data loss.
- Lost POST retries with identical v2 body remain idempotent.

### 5.3 Optimistic concurrency (`update_design` studio branch)

- Keep required `expected_revision` for studio working drafts.
- Before applying: if revision matches but fingerprint indicates downgrade/strip → **409** with payload explaining downgrade (do not apply).
- If revision matches and fingerprint equal (including back) → idempotent success (retry after lost response).
- If revision matches and fingerprint differs legally → apply update, bump stored revision from payload.

### 5.4 Conflict reconciliation

- FE `resolveDraftConflict` / Keep device / Use cloud remain **document-level** and must fingerprint both sides.
- “Equal” is only true when §5.1 fingerprints match (so a stripped local copy is **not** equal to a two-sided server copy).
- Keep device on a new client rebases full v2 document (front + back). Old client must not be offered a path that PUTs v1 over v2 (server rejects).

### 5.5 Back-only updates

- A save that changes only `back.strokes` / `back.fills` / `activeSide` must: advance `clientRevision`, change fingerprint, pass OCC, persist full document (both sides).
- Partial PATCH of one side is **out of scope** — always write the full `design_data` blob.

### 5.6 Alembic / Nginx / Cloudflare

**No new database migration** is justified by this architecture (JSON blob shape only). No Nginx/Cloudflare changes for V4J-A/B document work. Backend deploy of fingerprint/downgrade guards is a **separate authorized BE release** on the maint lineage before FE enablement.

---

## 6. Named saved designs (separate from working drafts)

### 6.1 Today

- Envelope schema: `fashionrise.saved_design.v1`.
- Nested `SavedDesignSnapshot`: `{ strokes, fills?, model, brush, dimmed }` — **not** a `StudioDraftDocument`.
- Rows are excluded from working-draft reconciliation (`draftKind` absent; top-level schema ≠ studio draft).
- Immutable after create; reopen copies snapshot into the singleton working draft via `workingDocumentFromSnapshot`.
- Idempotent save recovery uses `saveRequestId` + content fingerprint of the snapshot.

### 6.2 Two-sided saved designs

| Envelope | Snapshot |
|----------|----------|
| `fashionrise.saved_design.v1` | Front-only snapshots (legacy + front-only new saves). **No `back` key.** |
| `fashionrise.saved_design.v2` | May include `activeSide` + `back` bag with the same absent-vs-empty sentinel rules. Front ink remains `strokes`/`fills`. |

**Strict validation:**

- `parseSavedDesign` / `parseSavedDesignSnapshot` for v2: reject the whole row if `back` is present but malformed (do not drop back and open front-only).
- Old clients that only recognize `saved_design.v1`: two-sided rows appear as **non-openable / damaged or unknown**, never as a successfully opened front-only design that can be re-saved stripped.
- New clients: dual-read v1 + v2; write v1 for front-only saves; write v2 when back bag is present.

**Fingerprint / idempotent save:**

- Extend `snapshotFingerprint` with schema version + back sentinel.
- Backend saved-design create idempotency (by `saveRequestId` / content) must use the same fields so a lost response retry does not create a second row or a stripped row.

**Reopen:**

- v1 snapshot → working `draft.v1` (front only).
- v2 snapshot → working `draft.v2` with front + back (+ `activeSide` default front unless product chooses restore-last-side).

**Library preview:**

- Thumbnail / card always renders **front** (top-level strokes/fills) unless a later explicit “show back” UI is added.

**Export:**

- Default: active side (usually front).
- Dual export is WEB-V4J-C.

**Immutability:**

- Named saves are never updated in place to strip sides. Correction = new save. Server rejects any update path that would rewrite a v2 saved envelope as v1.

---

## 7. Library / runtime wiring (later — Stage D / WEB-V4J-B)

```ts
type BuiltinModelDef = {
  // ...existing fields
  rearCanvasSrc?: string // e.g. '/models/library/<id>-back.png'
}
```

- `canvasSrcForModel(id, side)` returns front today; rear only when `rearCanvasSrc` set.  
- Custom / blank / legacy without rear: Back control **disabled** with honest copy.  
- Design paper stays **768×1024**.  
- Existing Magic identity (`reference_model_id`) and garment-coverage fidelity fixes on the maint BE tip must be preserved when Magic later targets the active side only.

---

## 8. Editor / undo / autosave ownership

| Concern | Proposal |
|---------|----------|
| Undo stacks | Side-tagged single history so one Undo bar remains; switching sides must not pop the other side. |
| Autosave | Persist full v2 document (both sides); status label unchanged. |
| Conflict dialog | Fingerprint includes both sides; Keep device / Use cloud stays document-level; stripped local ≠ server. |
| Immersive / zoom | Side toggle next to Full screen in normal + immersive; viewport transform shared. |
| Dim reference | Applies to the active side’s croquis. |
| Model switch | Keep front artwork (existing confirm); disable Back if new model has no rear — **do not silently delete** back bag (orphan preserved offline or confirm-clear). |

---

## 9. Export & Magic boundaries

- **Export default:** active side PNG.  
- **Optional later:** Export both (V4J-C).  
- **Magic:** active side only; no paid calls in V4J-A. Preserve production identity + coverage prompt behavior when implemented.  
- **Pose / coverage:** operator-accepted on current maint BE; V4J-A does not change worker prompts.

---

## 10. Data-loss protection checklist

- [x] Legacy model IDs still resolve to original geometry paths.  
- [x] Front strokes/fills stay at top-level keys.  
- [x] Additive-only V1 optional `back` **rejected** as insufficient.  
- [x] Versioned `draft.v2` / `saved_design.v2` + dual-reader specified.  
- [x] Server reject-on-downgrade + fingerprint includes `back` / `activeSide` / schema.  
- [x] Absent `back` ≠ empty `back` in fingerprints.  
- [x] Named saved designs treated separately from working drafts.  
- [x] Public PR does **not** publish uncleared operator front master PNGs.  
- [x] Clean replacement branch has **no** front-master PNG commits in ancestry.  
- [x] No mirrored rear proposed as shippable asset.  
- [x] No Alembic migration required by documented architecture.  
- [ ] Backend fingerprint/OCC implementation + tests (Stage B).  
- [ ] FE dual-reader / flag (Stage D prep).  
- [ ] Operator confirms rear art + (if needed) master redistribution rights (Stage C).  
- [ ] Front/Back Studio UI after B + C (Stage D).

---

## 11. Delivery phases (current)

| Phase | Scope | Status |
|-------|--------|--------|
| **P1 / Magic blockers** | #51 Hand→Pencil, #59 identity, #60 narrow fill, #64 coverage, #39 pose | **CLOSED** — operator-accepted on prod FE `a740a9b7` / BE `12f7acdf…` |
| **Stage A — WEB-V4J-A** | Match fronts (manifest), rear specs, **safe** persistence architecture | **This clean docs PR — STOP for PM review** |
| **Stage B — BE persistence** | §5 fingerprint / reject-on-downgrade / OCC / idempotency on **maint** tip | Not started |
| **Stage C — Artwork gate** | Ten genuine rear companions; operator accept; provenance | **Not generated / not approved** |
| **Stage D — WEB-V4J-B UI** | Approved `-back.png`, library fields, Front/Back UI, v2 writers | Not started |
| **WEB-V4J-C** | Dual export / polish | Not started |

---

## 12. Out of scope / safety (this PR)

- No backend, worker, Alembic, Nginx, or Cloudflare **code** changes.  
- No paid OpenAI calls.  
- No production deploy / service restarts.  
- No Front/Back Studio UI implementation.  
- No rear PNG generation or shipping.  
- No uncleared front master binaries in the public tree.  
- No merge of PR #50 or of this replacement until Technical PM says so.  
- Do not auto-merge unrelated docs PRs (#44 / #46 / #49 / #53 / #63 / #66, etc.).

---

## 13. Compatibility test matrix

See `docs/web-v4j-a/COMPATIBILITY-TEST-MATRIX.md` for the full client × document × draft/saved × offline/conflict matrix required before Stage D enablement.
