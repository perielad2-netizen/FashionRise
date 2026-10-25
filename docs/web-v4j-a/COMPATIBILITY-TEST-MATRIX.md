# WEB-V4J-A — Front/Back compatibility test matrix

**Purpose:** Prove older clients cannot silently delete Back artwork, and that new clients round-trip two-sided documents across saves, restores, conflicts, and retries.  
**When to execute:** After backend fingerprint/downgrade guards land and before enabling Front/Back UI (WEB-V4J-B).  
**This PR:** documentation only — cases are the acceptance checklist for implementation PRs.

Legend: **PASS** = required outcome · **REJECT** = server 409 / client fail-closed · **N/A** = combination must not be reachable.

---

## 1. Actors

| Actor | Description |
|-------|-------------|
| **Old FE** | Production FE at `a740a9b7` (or any build that only parses `draft.v1` / `saved_design.v1` and front-only fingerprints) |
| **New FE** | Dual-reader v1+v2; writes v2 when back present; never strips on parse |
| **New BE** | Fingerprint includes schema + `activeSide` + back sentinel; reject-on-downgrade (Stage B, on maint lineage) |
| **Old BE** | Current production maint tip `12f7acdf…` front-only fingerprint — **must not** be paired with New FE Back UI |

---

## 2. Document shapes

| Doc | Schema | Back key |
|-----|--------|----------|
| **F1** | `studio.draft.v1` | absent (front-only working draft) |
| **F2** | `studio.draft.v2` | absent (front-only v2 — upgrade edge) |
| **T2** | `studio.draft.v2` | present, non-empty strokes/fills |
| **E2** | `studio.draft.v2` | present, empty `{ strokes:[], fills:[] }` |
| **S1** | `saved_design.v1` | snapshot front-only |
| **S2** | `saved_design.v2` | snapshot with `back` present |

---

## 3. Working draft — client × document

| # | Client | Server doc | Action | Required outcome |
|---|--------|------------|--------|------------------|
| W1 | Old FE | F1 | Edit front, autosave | PASS — today’s behavior |
| W2 | Old FE | T2 | Restore / open Studio | **Fail closed** — do not open as empty front; do not PUT stripped v1 |
| W3 | Old FE | T2 | If buggy client PUTs v1 without back | **REJECT** on New BE (`back_stripped` / schema downgrade); server T2 unchanged |
| W4 | New FE | F1 | Edit front only | PASS — may remain v1 |
| W5 | New FE | F1 | First Back enable / first back ink | PASS — upgrade to T2/E2; BE accepts upgrade under OCC |
| W6 | New FE | T2 | Back-only ink change | PASS — fingerprint changes; OCC advances; front unchanged |
| W7 | New FE | T2 | Front-only ink change | PASS — back preserved byte-stable in stored JSON |
| W8 | New FE | E2 vs F2 | Fingerprint equality | **Must differ** — empty back ≠ absent back |
| W9 | New FE | T2 | Clear all back ink intentionally | PASS — remains v2 with `back` key present (empty or cleared arrays), not downgraded to v1 |

---

## 4. Named saved designs

| # | Client | Row | Action | Required outcome |
|---|--------|-----|--------|------------------|
| N1 | Old FE | S1 | List / reopen / export | PASS — today’s behavior |
| N2 | Old FE | S2 | List / open | **Not openable as front-only** (unknown/damaged/hidden) — never re-save stripped |
| N3 | New FE | S1 | Reopen into working draft | PASS → working F1 (or front-only) |
| N4 | New FE | S2 | Reopen | PASS → working T2 with identical front+back |
| N5 | New FE | — | Save as design from T2 | PASS → new S2; preview uses **front**; `saveRequestId` idempotent |
| N6 | New FE | S2 | Lost HTTP response, retry same `saveRequestId` + fingerprint | PASS — single row, no duplicate, no strip |
| N7 | Any | S2 | Attempt update that rewrites envelope as v1 | **REJECT** — immutability / no downgrade |

---

## 5. Offline restore / lost response / OCC

| # | Scenario | Required outcome |
|---|----------|------------------|
| O1 | New FE offline edits T2 (back+front); reconnect; expected_revision matches | PASS — full T2 persisted |
| O2 | New FE offline; server already advanced; conflict UI | PASS — fingerprints include back; Keep device keeps both sides; Use cloud loads both sides |
| O3 | Old FE offline with stale F1 while server has T2; reconnect PUT | **REJECT** on New BE; server T2 preserved |
| O4 | Create working draft POST lost; retry identical T2 body | PASS — idempotent same id; fingerprint includes back |
| O5 | Create retry with same front as T2 but `back` omitted | **REJECT** — not treated as identical content |
| O6 | PUT retry identical body after 200 lost | PASS — same_content short-circuit includes back |
| O7 | PUT with matching revision but stripped back | **REJECT** even if front fingerprint matches old front-only hash |

---

## 6. Conflicts (two devices / two tabs)

| # | Device A | Device B | Required outcome |
|---|----------|----------|------------------|
| C1 | New FE edits back | New FE edits front | Conflict if concurrent; merge is **manual** Keep/Use; no auto strip |
| C2 | New FE has T2 | Old FE tab still open | Old FE cannot successfully overwrite; A’s T2 remains |
| C3 | Fingerprint equal including back | — | `equal: true`; no spurious conflict |
| C4 | Local stripped vs server T2 | — | `needsUserChoice: true`; choosing Keep on Old FE still **REJECT** at BE |

---

## 7. Previews & export

| # | Case | Required outcome |
|---|------|------------------|
| P1 | Library card for S2 | Renders **front** artwork |
| P2 | Export default from T2 on Back side | Exports **back** PNG (active side) |
| P3 | Export from T2 on Front | Exports front — identical pixels to pre-V4J for same front ink |
| P4 | Magic (when authorized) | Active side only; inactive side untouched on disk |

---

## 8. Rollout pairing gates

| BE | FE Back UI | Allowed? |
|----|------------|----------|
| Old BE | Off | Yes (today) |
| Old BE | On | **No** — back-only edits look like no-ops / data loss |
| New BE | Off | Yes — guards idle |
| New BE | On | Yes — target |

---

## 9. Minimum automated coverage (implementation PRs)

1. BE: fingerprint differs for absent vs empty vs non-empty back.  
2. BE: create/update reject v1 overwrite of v2/T2.  
3. BE: back-only update changes fingerprint and persists.  
4. BE: identical T2 create/PUT retry idempotent.  
5. FE: `parseStudioDraftDocument` v2 round-trip; v1 bitwise-stable on front fields.  
6. FE: old parser fixture proves strip would occur **without** server guard (characterization), and new writer never emits stripped bodies for T2.  
7. FE: saved_design v2 strict parse; v1 snapshot reopen.  
8. FE: conflict fingerprints include back.  
9. E2E matrix rows W3, W6, N2, N4, O3, O5, C2.
