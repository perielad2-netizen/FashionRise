# FashionRise QA V2 — reconciliation ledger

**Source of truth:** uploaded Master Plan + Tracker (2026-11-14).  
**Code baseline:** `main` `a78dfc89` (Batch B #305 merged).  
**PR #303:** open — native nav/push **not merged**; `NATIVE_PUSH_*` remain OFF.  
**Native evidence caveat:** many screenshots are from an older Android AAB; do not treat web tip deploy as proof the installed app already has the fix.

## Full 32-issue dispositions

| ID | Disposition | Batch | Notes |
|---|---|---|---|
| V2-0001 | **Confirmed** | C | Studio More: `pointerdown` + Escape dismiss |
| V2-0002 | **Confirmed** | C | Model cards: hover selection chrome gated to fine pointers |
| V2-0003 | **Confirmed** | C | FRONT/BACK: hover gated; active side keeps solid selected chrome |
| V2-0004 | **Confirmed** UX | C | Narrow Save keeps short label (not icon-only) |
| V2-0005 | **Fixed** | A | Immersive Save design label |
| V2-0006 | **Confirmed** | C | Gear opens Settings panel with named About/Privacy/Contact/Stars |
| V2-0007 | **Intentional** | B | Own-look self-vote blocked |
| V2-0008 | **Blocked** | B | TEMP native toggle OFF — reconcile with #303 (no second push impl) |
| V2-0009 | **Mitigated** | B | Sticky Add-friend + scrollable panel |
| V2-0010 | **Feature request** | E | Friend row actions |
| V2-0011 | **Confirmed** | B | Android adjustResize + visualViewport |
| V2-0012–0016, 0018–0020 | **A** | A | Merged #304 |
| V2-0017 | **Investigation** | D | AI FRONT/BACK |
| V2-0021 | **Feature request** | E | Editable canvas props |
| V2-0022 | **Confirmed** | C | Autosave status max-width widened beside Stars |
| V2-0023 | **Confirmed** | C | Kind-aware brush tip preview |
| V2-0024 | **Confirmed** | C | Airbrush draft/stamp presence boosted |
| V2-0025 | **Confirmed** | C | Texture helper copy; charcoal accent slider |
| V2-0026 | **Feature request** | E | Brush explainers |
| V2-0027 | **Confirmed** | C | Wheel hint gated to fine pointer; mobile slider copy |
| V2-0028 | **Confirmed** | C | Pattern scale Fine↔Coarse + explanation |
| V2-0029 | **Confirmed** | C | Brush color on brush sheet + Materials link |
| V2-0030–0032 | **Feature** | E | Roadmap |
| **V2-0033** | **Confirmed** | B | Native Media/Share download; recursive `fr-dl/` |
| **V2-0034** | **Confirmed** P1 | C | Personal My Model FRONT-only; coerce activeSide on pin/restore; Flip hidden; Back bags preserved |

## 21 CTL proposals

Roadmap only. Not in Batch C.

## Batch C PR scope

Studio/mobile polish: V2-0001–0004, 0006, 0022–0025, 0027–0029.  
**+ V2-0034** personal model FRONT-only (Android: created My Model missing after return because canvas stayed on BACK).

**Out of scope:** Batches D–E, CTL-*, push enable, store submit, merging #303.
