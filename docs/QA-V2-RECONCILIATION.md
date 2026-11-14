# FashionRise QA V2 — reconciliation ledger

**Source of truth:** uploaded Master Plan + Tracker (2026-11-14).  
**Code baseline:** Batch E implementation — V2-0030 rect eraser after #308 planning merge.  
**PR #303:** open — native nav/push **not merged**; `NATIVE_PUSH_*` remain OFF.  
**Native evidence caveat:** many screenshots are from an older Android AAB; do not treat web tip deploy as proof the installed app already has the fix.

One row per ID. Earlier findings are preserved; later batch notes update disposition without collapsing IDs.

## Full issue dispositions (V2-0001 … V2-0034)

| ID | Disposition | Batch | Notes |
|---|---|---|---|
| V2-0001 | **Confirmed** | C | Studio ⋯ overflow separate from #302 shell menus; More: `pointerdown` + Escape dismiss |
| V2-0002 | **Confirmed** | C | Dual selection highlight risk; model-card hover chrome gated to fine pointers |
| V2-0003 | **Confirmed** | C | Rapid FRONT/BACK pressed-state; hover gated; active side keeps solid selected chrome |
| V2-0004 | **Confirmed** UX | C | Save discoverability; narrow Save keeps short label (not icon-only) |
| V2-0005 | **Fixed** | A | Immersive Save reused autosave “Saved…” label — always labels **Save design** |
| V2-0006 | **Confirmed** | C | Gear → Settings panel with named About / Privacy / Contact / Stars |
| V2-0007 | **Intentional** | B | Own looks: likes/scores from others only; UI hint preserved; no self-vote |
| V2-0008 | **Blocked** | B | TEMP native push toggle OFF + copy; **reconcile with PR #303** (reuse its push path — no second impl); flags not enabled |
| V2-0009 | **Mitigated** | B | Sticky Add-friend + scrollable friends body; no hidden-list defect proven |
| V2-0010 | **Feature request** | E | Friend row actions — planning (read-only profile first); privacy/auth gated |
| V2-0011 | **Confirmed** | B | Android `adjustResize` + visualViewport pad / scrollIntoView for Add friend |
| V2-0012 | **Fixed** | A | Mid-session `apiRequest` refresh-on-401 + session-expired event |
| V2-0013 | **Fixed** | A | Same root as 0012 + honest ack path; refresh race amendment (discard stale after logout/switch) |
| V2-0014 | **Unconfirmed defect** (verified safe) | A | Distinct titles/IDs already; regression tests added |
| V2-0015 | **Rejected hypothesis** | A | No title-based overwrite; regression only |
| V2-0016 | **Confirmed mechanism** | A | Fingerprint+OCC+dialog already non-destructive; no silent overwrite; no speculative auto-resolve |
| V2-0017 | **Improved** (bounded) | D | Dual Magic: Back gets Front pair reference + stronger shared-spec/pair prompts; `pair_reference_fingerprint` in prompt identity; targeted Back retry preserves good Front; Ready ≠ perfect match; no extra Stars on failed-key replay |
| V2-0018 | **Security review — not exploit** | A | Parameterized + React text; synthetic tests |
| V2-0019 | **Security review — not exploit** | A | Same as 0018 |
| V2-0020 | **Security review — not exploit** | A | Same as 0018 |
| V2-0021 | **Feature request** | E | Canvas props — prefer honest read-only labels before risky resize |
| V2-0022 | **Confirmed** | C | Header clip; autosave status max-width widened beside Stars |
| V2-0023 | **Confirmed** | C | Brush footprint; kind-aware brush tip preview |
| V2-0024 | **Confirmed** | C | Airbrush draft/stamp presence boosted |
| V2-0025 | **Confirmed** | C | Texture helper copy; charcoal accent slider (0% texture look clarified) |
| V2-0026 | **Feature request** | E | Brush explainers — truthful short copy + touch-safe hints only |
| V2-0027 | **Confirmed** | C | Mouse-wheel hint gated to fine pointer; mobile slider copy |
| V2-0028 | **Confirmed** | C | Pattern scale Fine↔Coarse + explanation |
| V2-0029 | **Confirmed** | C | Brush color on brush sheet + Materials link |
| V2-0030 | **Fixed** P1 | E | Rectangular eraser (`rectErase`): clips active-side strokes/fills **inside** the selection (crossing segments kept outside); layer-aware; Undo/Redo; Clear + freehand erase kept |
| V2-0031 | **Feature request** P1 | E | Home before/after gallery — authorized examples only; reduced-motion |
| V2-0032 | **Feature / copy** | E | Home value copy — can ship before carousel if truthful |
| V2-0033 | **Confirmed** P1 | B | My Looks Download no-op on Android WebView `<a download>`; Capacitor Media (+ Share fallback) + recursive `fr-dl/` + `apiRequestBlob` refresh |
| V2-0034 | **Confirmed** P1 | C | Personal My Model is FRONT-only (one front image); pin/restore coerce Front; Flip hidden/disabled; Back bags preserved; create does not auto-select — Use in Studio is explicit |

## 21 CTL proposals

Remain **roadmap only** (CTL-M01…M06, CTL-B01…B07, CTL-T01…T08). Not defects; not in Batch A–C.

## Batch A PR scope (merged #304)

1. Mid-session `apiRequest` refresh-on-401 + session-expired event (V2-0012, V2-0013).  
2. Immersive toolbar always labels explicit save as **Save design** (V2-0005).  
3. Synthetic regression/security tests for titles/comments/friend search (V2-0014/15/18/19/20).  
4. Document draft-conflict non-destructive behavior (V2-0016) — no speculative auto-resolve.  
5. Refresh race amendment: discard stale refresh after logout/account switch.

## Batch B PR scope (merged #305)

1. V2-0007 — verify own-look reaction restriction + copy (no self-vote regression).  
2. V2-0008 — TEMP native toggle OFF + messaging; **must reconcile with PR #303** (use #303 native push — do not duplicate); **do not enable** push flags.  
3. V2-0009 / V2-0011 — Friends sticky add-row + Android keyboard (`adjustResize` + visualViewport).  
4. V2-0010 — remains Batch E feature request.  
5. V2-0033 — platform-aware My Looks / Magic image save (Media gallery + Share file; web anchor unchanged); `fetchJobImageBlob` via `apiRequestBlob` with Batch A session isolation.

## Batch C PR scope (merged #306)

Studio/mobile polish: V2-0001–0004, 0006, 0022–0025, 0027–0029.  
**+ V2-0034** personal model FRONT-only (Android: created My Model missing after return because canvas stayed on BACK).

## Batch D PR scope (merged #307)

V2-0017 AI FRONT/BACK consistency (bounded):
1. Investigation: Dual jobs shared text `shared_garment_spec` but Back only saw its own sketch — divergence / invented bodysuit risk.  
2. Back Dual enqueue attaches Front sketch as `pair_reference_base64` (Image 2 when no fabric swatch).  
3. Stronger Back vision/edit + FRONT/BACK PAIR text contracts; shared-spec details mark `pair_mode` / no-bodysuit.  
4. `pair_reference_fingerprint` included in `_prompt_identity_fingerprint` (same-key ≠ mismatched Front pair).  
5. Targeted Back retry reuses shared spec + Front pair capture; does not overwrite a good Front.  
6. Billing: failed-key replay still returns original job (no new charge); notice clarifies Ready is per-side.

## Batch E planning (feature backlog — PM gate)

Master Plan exit: **PM-approved spec and acceptance criteria; independent PRs.**  
Not defects. Do **not** enable push, change Stars billing, or submit store builds here.

| Priority | ID | Proposed slice | Risk / gate |
|---|---|---|---|
| P1 | V2-0030 | Rectangular-area eraser with Undo; keep Clear canvas + confirm | Destructive; layer-aware; no silent global clear |
| P1 | V2-0031 | Home before/after carousel of authorized product examples | No fabricated AI claims; perf + reduced-motion |
| P2 | V2-0032 | Home value copy + clear Start Creating CTA | Can ship ahead of carousel if copy is truthful |
| P2 | V2-0026 | Short brush-setting explainers (touch-safe) | Only describe real effects |
| P2 | V2-0021 | Label immutable canvas props **or** limited editable dims | Avoid corrupting saved drawings via resize |
| P2 | V2-0010 | Friend row → read-only profile / published looks | Privacy/auth; remove stays confirmed |

## Batch E — V2-0030 Rectangular eraser

- New Studio tool `rectErase` (rail + immersive); drag marquee in design space.
- Pure `eraseArtworkInRect` **clips** strokes at selection boundaries (including segments with both endpoints outside) and punches fill holes so exterior artwork remains.
- Layer-aware; ink layer punches fills; shade/highlight leave fills.
- Commits through existing StrokeHistory + draft document path (save/reopen preserved).
- Freehand Eraser and Clear canvas unchanged.

**Next E slices (separate PRs):** V2-0032 Home copy → V2-0026 brush explainers.  
**Still out of scope:** CTL-*, push enable, store submit, merging #303.
