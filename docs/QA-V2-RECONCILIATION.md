# FashionRise QA V2 — reconciliation ledger

**Source of truth:** uploaded Master Plan + Tracker (2026-11-14).  
**Code baseline:** `main` `d7f61f9e` (includes #302).  
**PR #303:** open @ `4b433a95` — native nav/push **not merged**; `NATIVE_PUSH_*` remain OFF.  
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
| V2-0007 | **Intentional** until other-user repro fails | B | Own looks: likes/scores from others only |
| V2-0008 | **Confirmed** / blocked by native setup | B | Old AAB + flags OFF; needs #303 + operator creds + new binary |
| V2-0009 | **Unconfirmed** | B | Screenshot showed friends present |
| V2-0010 | **Feature request** | E | Friend row actions |
| V2-0011 | **Confirmed** | B | Android keyboard vs Add friend |
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

## 21 CTL proposals

Remain **roadmap only** (CTL-M01…M06, CTL-B01…B07, CTL-T01…T08). Not defects; not in Batch A.

## Batch A PR scope

1. Mid-session `apiRequest` refresh-on-401 + session-expired event (V2-0012, V2-0013).  
2. Immersive toolbar always labels explicit save as **Save design** (V2-0005).  
3. Synthetic regression/security tests for titles/comments/friend search (V2-0014/15/18/19/20).  
4. Document draft-conflict non-destructive behavior (V2-0016) — no speculative auto-resolve.

**Out of scope / stop line:** native push enablement, Android billing gates, store submit, Batches B–E.
