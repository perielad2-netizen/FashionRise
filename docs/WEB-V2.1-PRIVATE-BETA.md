# WEB-V2.1 / WEB-V2.1A / WEB-V2.1B / WEB-V2.1C — Private beta draft persistence & tablet readiness

**Date:** 2026-10-19  
**Branch:** `cursor/web-ui-reboot` (draft PR #9)  
**Scope:** Production `/studio` only. No Magic. No merge/deploy. No redesign.

## WEB-V2.1C — conflict resolution final gate

- **Keep this device** rebases the chosen local draft to `max(local, server) + 1` and saves with `expected_revision` equal to the server revision just seen. Strokes and brush settings are preserved. A concurrent server advance returns 409 and reopens the choice; it does not overwrite.
- **Use cloud draft** replaces the IndexedDB recovery record even when the cloud revision is numerically lower. Saved is shown only after that replacement succeeds. A failed IndexedDB write stays on Save failed and keeps the dialog.
- Automatic cloud writes stay suspended while a conflict is unresolved.
- Create/reconcile responses whose acknowledged content differs from the local document are conflicts, not Saved.

## WEB-V2.1B amendment (final persistence hardening)

Closes the remaining PM correctness risks from WEB-V2.1A review.

### 1. Monotonic local recovery (P0)

- `writeLocalDraft` never replaces a newer `clientRevision` document with an older cloud/IDB response.
- Delayed cloud completion for edit A cannot overwrite local recovery for edit B.
- Regression: edit A → delayed response → edit B → A completes → refresh path keeps B.

### 2. Atomic Studio create (P0)

- Per-owner `pg_advisory_xact_lock` around Studio working-draft create/reconcile.
- Concurrent POSTs cannot insert multiple working drafts.
- Identical retries are idempotent.
- Equal-revision, different-content creates return HTTP **409** (no silent overwrite).
- Lower-revision create retries still do not clobber newer server work.

### 3. Required `expected_revision` for Studio updates (P0)

- Updates to existing Studio working drafts **require** `expected_revision`.
- Stale tokens and non-advancing content changes at the same revision → **409**.
- Non-Studio designs remain unversioned-compatible when `expected_revision` is omitted.

### 4. Honest synced revision on fingerprint no-op (P1)

- When cloud fingerprint is unchanged, return the last **server-acknowledged** revision — never the unsent local `clientRevision`.
- Prevents edit → revert → edit spurious 409 cycles.

### 5. No blind reconcile after non-409 failures

- Preferred-design PUT failures other than 404/409 do **not** fall through to list-and-overwrite.
- Lost-create reconcile only advances with a known server revision token.

## WEB-V2.1A amendment (data-loss prevention)

### Authoritative snapshot saves

- `authoritativeDocRef` updated before React state; cloud flush reads that ref only.

### Durable local recovery + honest status

- IndexedDB write on every committed edit.
- “Saved on this device” only after IndexedDB OK; never “Saved” while newer pending.

### Optimistic concurrency baseline

- Row lock + 409 payload; operator chooses on conflict.

### Custom references (beta)

- Persistent uploads **disabled** (`/static/uploads` not owner-private). Session blob only.

## Verification

| Gate | Result |
|------|--------|
| Frontend `npm test` | **Pass — 63 tests / 21 files** |
| `npm run build` | **Pass** |
| `npm run lint` | **Pass** (pre-existing warnings only) |
| Backend pytest (isolated Postgres `fashionrise_test`) | **Pass — 44** incl. 10 Studio concurrency/create |
| Production DB | **Not used** |
| Unity / PickWise / synagogue | Untouched |
| OpenAI / paid AI | None |

### Key regressions

| Case | Coverage |
|------|----------|
| Delayed cloud A vs local B | `draftPersistence.test.ts` |
| Fingerprint no-op keeps server rev | `draftPersistence.test.ts` |
| Non-409 preferred PUT no blind overwrite | `draftPersistence.test.ts` |
| Concurrent identical creates → one row | `test_studio_draft_concurrency.py` |
| Equal-rev different-content create → 409 | live API |
| Studio PUT without `expected_revision` → 409 | live API |
| Non-Studio PUT without revision still OK | live API |

## Deployment readiness

**Persistence safety gate is ready for operator live tablet testing.** Still not deploy-ready until:

1. Live tablet acceptance (two-tab conflict, refresh-after-draw, offline) on staging
2. Private-beta invite / access gating
3. Product decision on custom-reference privacy (disabled, not privatized)
4. DNS/deploy to fashionrise.app — not in this milestone

**STOP FOR PM REVIEW.** Do not merge PR #9, expose the app, or enable paid AI.
