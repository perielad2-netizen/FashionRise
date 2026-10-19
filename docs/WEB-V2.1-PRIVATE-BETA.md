# WEB-V2.1 / WEB-V2.1A — Private beta draft persistence & tablet readiness

**Date:** 2026-10-19  
**Branch:** `cursor/web-ui-reboot` (draft PR #9)  
**Scope:** Production `/studio` only. No Magic. No merge/deploy. No redesign.

## WEB-V2.1A amendment (data-loss prevention)

Visual design remains approved. This amendment fixes verified draft-persistence risks before merge or beta deployment.

### 1. Authoritative snapshot saves (P0)

- `useStudioEditor` keeps an `authoritativeDocRef` updated **before** React state on restore and on every committed edit.
- Cloud flushes read **only** that ref (never reconstruct from uncommitted React state after `applyDocument`).
- Save chain remains serialized; API writes stay debounced (~1.6s).

### 2. Durable local recovery + honest status

- Every committed edit writes IndexedDB immediately (`persistLocalRecovery`), independent of API debounce.
- Status rules:
  - `pending` — edit committed, local write in flight / not yet confirmed
  - `local-only` / “Saved on this device” — **only** after IndexedDB confirms success
  - `saving` — cloud write in flight
  - `saved` — cloud acknowledged **and** no newer pending authoritative changes
  - `error` — local and/or cloud failed; never claim Saved while newer edits remain pending
- Handles IndexedDB unavailable, quota errors, refresh, logout flush, offline edits, delayed responses, interrupted saves.

### 3. Real optimistic concurrency

- Studio `PUT /designs/{id}` accepts `expected_revision` (stored `clientRevision`).
- Backend `SELECT … FOR UPDATE` + HTTP **409** with payload `{ expected_revision, current_revision, design }` when stale.
- Omitting `expected_revision` preserves compatibility for non-Studio design updates.
- On conflict, **both** copies are retained until the operator chooses Keep this device / Use cloud draft. No auto-overwrite because a local revision is higher.
- Boot restore uses content fingerprint only: any content mismatch → conflict dialog.

### 4. Private-reference handling (beta)

- Persistent custom-reference uploads are **disabled** for private beta.
- Reason: `POST /uploads/image` is authenticated, but `/static/uploads` retrieval is not owner-authorized — URLs are not private.
- Session blob preview still works; cloud payloads strip `customReferenceUrl` / `customReferenceKey`.
- UI notice states session-only limitation; we do **not** claim these images are private.

### 5. Robust initial draft creation

- `POST /designs` for Studio working drafts reconciles to the existing owner-scoped draft (no duplicates).
- Stale create retries with a lower `clientRevision` do not clobber a newer server draft.
- Client `ensureStudioDraft` lists/updates after a lost create response.

## What shipped (WEB-V2.1 baseline + 2.1A)

### Draft persistence (owner-scoped)

- Reuses authenticated FastAPI `POST/GET/PUT /api/v1/designs` (+ `GET /designs/my`)
- Schema `fashionrise.studio.draft.v1` / `draftKind: studio_working_draft`
- One working draft per user
- Debounced serialized API autosave from authoritative snapshot
- Immediate IndexedDB recovery mirror on each edit

### Model switching / tablet brush panel

Unchanged from WEB-V2.1: Keep/Clear/Cancel model switch; narrow Brush panel overlay; Magic notice-only.

## Drawing QA

### Automated / simulated (this environment)

| Check | Result |
|-------|--------|
| Pointer unit rules (`pointerSession`) | Covered by existing unit tests |
| Authoritative restore vs empty React state | Regression test `authoritativeSave.test.ts` |
| Conflict dialog on divergent local/server | Frontend + live API 409 tests |
| Stale PUT cannot overwrite newer draft | Live Postgres test |
| Lost create reconcile (no duplicate drafts) | Live Postgres test |
| IndexedDB unavailable / failed writes | Unit tests |
| Custom ref not persisted privately | `documentForCloud` + disable upload |
| Real stylus / multi-touch hardware | **Not available in this VM** |
| Real tablet orientation + palm rejection | **Manual acceptance required** |

### Manual tablet acceptance checklist (operator)

1. Login → Studio restores previous private draft
2. Draw; hard-refresh immediately — strokes return from local and/or cloud
3. Two browser tabs: edit in both → stale tab gets conflict / 409; choose explicitly
4. Offline edit → “Saved on this device” only if IndexedDB succeeds; reconnect syncs
5. Custom reference → session preview only; notice explains no private server storage
6. Confirm Magic still shows later-milestone notice (no AI traffic)

## Security notes

- Drafts: `visibility: "private"`, `status: "draft"`, owner-scoped endpoints
- Optimistic concurrency on Studio updates (`expected_revision`)
- Custom reference **uploads disabled** for beta (not owner-private at `/static/uploads`)
- Magic / Generate with AI remain notice-only (no paid calls)
- No public registration, gallery publish, or social features added

## Verification

| Gate | Result |
|------|--------|
| Frontend `npm test` | **Pass — 52 tests / 20 files** |
| `npm run build` | **Pass** |
| `npm run lint` | **Pass** (pre-existing warnings only) |
| Backend pytest (isolated Postgres `fashionrise_test`) | **Pass — 39** incl. 5 Studio concurrency/reconcile |
| Production DB | **Not used** |
| Unity / PickWise / synagogue | Unchanged / untouched |
| OpenAI / paid AI | None |

## Deployment readiness

**Not ready to deploy.** Persistence safety is improved for private beta engineering review, but:

1. Operator must run manual tablet acceptance with a live API + Postgres
2. Private-beta invite / access gating still pending
3. Custom reference privacy remains a product gap (disabled, not privatized)
4. DNS/deploy to fashionrise.app not in this milestone

**STOP FOR PM REVIEW.** Do not merge PR #9, expose the app, or enable paid AI.
