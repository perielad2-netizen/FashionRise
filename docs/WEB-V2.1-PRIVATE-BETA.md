# WEB-V2.1 — Private beta draft persistence & tablet readiness

**Date:** 2026-10-19  
**Branch:** `cursor/web-ui-reboot`  
**Scope:** Production `/studio` only. No Magic. No merge/deploy. No redesign.

## What shipped

### Draft persistence (owner-scoped)

- Reuses authenticated FastAPI `POST/GET/PUT /api/v1/designs` (+ `GET /designs/my`)
- Stores structured payload in `design_data` with schema `fashionrise.studio.draft.v1`
- One working draft per user (tracked by `localStorage` design id + IndexedDB recovery)
- Debounced autosave (~1.6s); skips redundant PUTs when fingerprint unchanged
- Save queue serializes overlapping requests
- Status chrome: Restoring / Saving / Saved / Save failed (+ Retry) / Saved on this device

### IndexedDB recovery + conflicts

- Local mirror written on every save attempt
- On boot: compare local vs server `clientRevision`
- Newer side wins automatically
- Same revision + different content → explicit conflict dialog (never silent overwrite)

### Custom references

- Uploads via authenticated `POST /api/v1/uploads/image` when API reachable
- Stores `customReferenceUrl` + `customReferenceKey` in draft
- If upload fails: local blob preview for the session, with explicit notice (not a silent broken restore)
- If restored URL fails to load: clear warning; strokes preserved

### Model switching

- Changing Female/Male/Custom/Blank with existing ink opens confirm dialog:
  - Keep strokes / Clear strokes / Cancel

### Tablet brush panel

- Narrow screens: floating pencil card hidden
- **Brush panel** opens as bottom overlay with scrim + Done (does not push toolbar/canvas layout)

## Screenshots

| View | Path |
|------|------|
| 1536×1024 | `/opt/cursor/artifacts/screenshots/studio-webv21-1536x1024.png` |
| 768×1024 | `/opt/cursor/artifacts/screenshots/studio-webv21-768x1024.png` |
| 390×844 | `/opt/cursor/artifacts/screenshots/studio-webv21-390x844.png` |
| 390 brush overlay | `/opt/cursor/artifacts/screenshots/studio-webv21-390x844-brush-overlay.png` |
| Model switch | `/opt/cursor/artifacts/screenshots/studio-webv21-model-switch.png` |

## Drawing QA

### Automated / simulated (this environment)

| Check | Result |
|-------|--------|
| Pointer unit rules (`pointerSession`) | Covered by existing unit tests |
| Hold-to-draw / release-stop (Playwright mouse) | Verified in prior WEB-V2 + smoke here |
| Model switch confirmation | Verified (screenshot) |
| Save status after mocked restore | Verified (“Saved”) |
| Brush overlay on 390×844 | Verified (screenshot) |
| Real stylus / real multi-touch hardware | **Not available in this VM** |
| Real tablet orientation + palm rejection | **Manual acceptance required** |

### Manual tablet acceptance checklist (operator)

1. Login → Studio restores previous private draft
2. Draw with finger and (if available) stylus; release outside canvas stops ink
3. Two-finger scroll/pan on page chrome does not paint
4. Eraser removes ink only; undo/redo/clear behave
5. Rotate / resize browser; canvas remasures without duplicate handlers
6. Toggle Brush panel overlay; drawing area remains usable after Done
7. Switch model with strokes → choose Keep / Clear intentionally
8. Upload custom image; refresh; image returns if upload/API healthy
9. Kill network mid-edit → local recovery; reconnect syncs without silent wipe
10. Confirm Magic still shows later-milestone notice (no AI traffic)

## Security notes

- Drafts created with `visibility: "private"` and `status: "draft"`
- Updates/reads go through owner-scoped design endpoints
- Uploads require auth
- Magic / Generate with AI remain notice-only (no paid calls)
- No public registration, gallery publish, or social features added

## Verification

| Gate | Result |
|------|--------|
| `npm test` | Pass (**40**) |
| `npm run build` | Pass |
| `npm run lint` | Pass (warnings only) |
| `git diff --check` | Clean |
| Backend pytest | **Blocked** — Postgres not running in this environment; **no backend code changes** |
| Unity | Unchanged |
| OpenAI / paid AI | None |

## Deployment readiness

**Not ready to deploy.** Private draft persistence is implemented against the existing API, but:

1. Operator must run manual tablet acceptance with a live API + Postgres
2. End-to-end save/restore should be validated against a real fashionrise.app staging stack
3. Private-beta access controls / invite gating still pending
4. DNS/deploy to fashionrise.app not in this milestone

**STOP FOR PM REVIEW.**
