# FashionRise QA V2 — reconciliation ledger

**Source of truth:** uploaded Master Plan + Tracker (2026-11-14).  
**Code baseline:** `main` `6a405ccf` (Batch A #304 merged).  
**PR #303:** open — native nav/push **not merged**; `NATIVE_PUSH_*` remain OFF.  
**Native evidence caveat:** many screenshots are from an older Android AAB; do not treat web tip deploy as proof the installed app already has the fix.

## Full 32-issue dispositions (engineered against current `main`)

| ID | Disposition | Batch | Notes vs current code / #302 |
|---|---|---|---|
| V2-0001 | **Confirmed** (fix in C) | C | Studio ⋯ overflow separate from #302 shell menus |
| V2-0002 | **Confirmed** (fix in C) | C | Dual selection highlight risk |
| V2-0003 | **Unconfirmed** / likely CSS pressed state | C | Investigate rapid FRONT/BACK |
| V2-0004 | **Confirmed** UX | C | Save discoverability |
| V2-0005 | **Confirmed** UX confusion | A | Immersive Save reused autosave “Saved…” label — fixed in Batch A PR |
| V2-0006 | **Confirmed** UX | C | Gear → About |
| V2-0007 | **Intentional** (verified) | B | Own looks: likes/scores from others only; UI hint preserved; no self-vote |
| V2-0008 | **Confirmed** / blocked by native setup | B | TEMP native toggle OFF + copy in RunwayScreen; **reconcile with PR #303** (reuse its push path — no second impl); flags not enabled |
| V2-0009 | **Mitigated UX** | B | Sticky Add-friend + scrollable friends body; no hidden-list defect proven |
| V2-0010 | **Feature request** | E | Friend row actions — not in Batch B |
| V2-0011 | **Confirmed** | B | Android `adjustResize` + visualViewport pad / scrollIntoView for Add friend |
| V2-0012 | **Confirmed** | A | No mid-session refresh-on-401 — fixed in Batch A PR |
| V2-0013 | **Confirmed** | A | Same root cause as 0012 + honest ack path already strong |
| V2-0014 | **Unconfirmed defect** (verify) | A | Distinct titles/IDs already; regression tests added |
| V2-0015 | **Rejected hypothesis** | A | No title-based overwrite; regression only |
| V2-0016 | **Confirmed mechanism / investigate false positives** | A | Fingerprint+OCC+dialog already non-destructive; no silent overwrite |
| V2-0017 | **Confirmed** quality investigation | D | Separate AI batch |
| V2-0018 | **Security review — not exploit** | A | Parameterized + React text; synthetic tests |
| V2-0019 | **Security review — not exploit** | A | Same |
| V2-0020 | **Security review — not exploit** | A | Same |
| V2-0021 | **Feature request** | E | Editable canvas props |
| V2-0022 | **Confirmed** | C | Header clip |
| V2-0023 | **Feature / UI** | C | Brush footprint |
| V2-0024 | **Confirmed** | C | Airbrush preview |
| V2-0025 | **Unconfirmed** | C | 0% texture look |
| V2-0026 | **Feature request** | E | Brush explainers |
| V2-0027 | **Confirmed** copy | C | Mouse-wheel hint on mobile |
| V2-0028 | **Feature / UI** | C | Pattern scale explain |
| V2-0029 | **Feature / UX** | C | Direct brush color |
| V2-0030 | **Feature request** | E | Rectangular eraser |
| V2-0031 | **Feature request** | E | Home gallery |
| V2-0032 | **Feature / copy** | E | Home value copy |

## New issues after V2-0032

| ID | Disposition | Batch | Notes |
|---|---|---|---|
| V2-0033 | **Confirmed** P1 | B | My Looks Download no-op on Android WebView `<a download>`; Capacitor Media (+ Share fallback) + `apiRequestBlob` refresh |

## 21 CTL proposals

Remain **roadmap only** (CTL-M01…M06, CTL-B01…B07, CTL-T01…T08). Not defects; not in Batch A/B.

## Batch A PR scope (merged #304)

1. Mid-session `apiRequest` refresh-on-401 + session-expired event (V2-0012, V2-0013).  
2. Immersive toolbar always labels explicit save as **Save design** (V2-0005).  
3. Synthetic regression/security tests for titles/comments/friend search (V2-0014/15/18/19/20).  
4. Document draft-conflict non-destructive behavior (V2-0016) — no speculative auto-resolve.  
5. Refresh race amendment: discard stale refresh after logout/account switch.

## Batch B PR scope

1. V2-0007 — verify own-look reaction restriction + copy (no self-vote regression).  
2. V2-0008 — TEMP native toggle OFF + messaging; **must reconcile with PR #303** (use #303 native push — do not duplicate); **do not enable** push flags here.  
3. V2-0009 / V2-0011 — Friends sticky add-row + Android keyboard (`adjustResize` + visualViewport).  
4. V2-0010 — remains Batch E feature request.  
5. V2-0033 — platform-aware My Looks / Magic image save (Media gallery + Share file; web anchor unchanged); `fetchJobImageBlob` via `apiRequestBlob` with Batch A session isolation.

**Out of scope / stop line:** Batches C–E, CTL-*, native push enablement, Android billing gates, store submit, merging #303.
