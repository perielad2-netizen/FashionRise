# WEB-V3A — Export, Save & My Designs: design and QA report

**Branch:** `cursor/web-v3a-design-library-77c6`, draft PR [#13](https://github.com/perielad2-netizen/FashionRise/pull/13), based on `main` `f8a5b222`.
**Status:** waiting for PM **re-review** after the focused safety amendment. Not merged, not deployed.
**Scope:** frontend (`web-ui/`), one narrowly justified backend create/reconcile safety change (no new endpoint, no migration), plus backend regression tests. No Nginx, Cloudflare, AI, upload, or registration changes.

A signed-in user can now:

1. Draw in Studio.
2. **Export PNG**: a real 768×1024 PNG file, rendered on the device.
3. **Save as design**: a named, owner-private snapshot stored separately from the working draft.
4. Browse **My Designs**: the working draft plus saved designs, with previews.
5. **Open** a saved design back into Studio, without silently losing unsaved work.

---

## 1. Working draft and saved designs

### Rules carried over unchanged

- Each user still has **exactly one Studio working draft**: schema `fashionrise.studio.draft.v1`, `metadata.draftKind = "studio_working_draft"`.
- Its create, autosave, reconcile, IndexedDB recovery, `expected_revision` optimistic concurrency, and conflict dialog are unchanged.
- The backend recognises the working draft only by:
  - `metadata.draftKind == "studio_working_draft"`, or
  - a **top-level** `design_data.schema == "fashionrise.studio.draft.v1"`.

  Both checks live in `_is_studio_payload` and `_is_studio_working_draft` in `backend/app/services/design_service.py`.

### Saved-design record format

A saved design is a separate private `garment_designs` row created through the existing `POST /api/v1/designs`.

```jsonc
{
  "title": "Runway coat",                 // validated, ≤ 80 chars
  "garment_category": "studio",
  "visibility": "private",                // always private
  "status": "draft",
  "design_data": {
    "schema": "fashionrise.saved_design.v1",   // distinct top-level schema
    "saveRequestId": "<uuid per Save dialog>",
    "savedAt": "2026-10-20T10:14:03.120Z",
    "sourceRevision": 7,                       // working-draft revision it was taken from (informational)
    "snapshot": {
      "strokes": [ /* exact Stroke objects: id, tool, points, color, size, opacity */ ],
      "model": "female",                       // female | male | custom | blank
      "brush": { /* tool, size, color, opacity as in Studio */ },
      "dimmed": false
    }
  },
  "metadata": {
    "designKind": "saved_design",              // never "studio_working_draft"
    "envelope": "fashionrise.saved_design.v1",
    "saveRequestId": "<uuid>",
    "savedAt": "…",
    "model": "female",
    "strokeCount": 12
  }
}
```

**Why this never touches the working-draft singleton:**

- No `draftKind` is set.
- The top-level schema is not the Studio schema.
- The snapshot has no `schema` or `clientRevision` field.

The backend therefore treats the row as an ordinary non-Studio design: plain insert, no per-owner advisory lock, no reconcile, no revision rules. `backend/tests/test_saved_design_isolation.py` proves this against live FastAPI and PostgreSQL. It covers both the `draftKind` marker and a nested Studio `schema`.

### Security properties

| Property | How it is enforced |
|---|---|
| Owner-private | `visibility: "private"` on create. `/designs/my` and `/designs/{id}` only return private rows to their owner; backend test `test_saved_designs_are_owner_private`. The client also rejects any row whose `user_id` is not the signed-in user, or that is not private. |
| No public exposure | No publish action and no Gallery call. `/api/v1/gallery` is not used. |
| No custom images stored | The snapshot stores the model id only. Session custom-reference object URLs are never persisted, and the dialog says so. |
| Strict parsing | `parseSavedDesign` rejects the **whole** snapshot on any bad stroke (NaN point, unknown tool, non-hex colour, unknown model, bad brush) instead of silently dropping ink. Over 5,000 strokes or over 1.5 M points is rejected. Damaged rows are listed separately as "could not be shown" and cannot be opened. |
| Titles are text | Rendered as React text, never HTML. Trimmed, whitespace collapsed, 1–80 characters, control characters rejected, non-Latin allowed. |

### Compatibility

- **Older clients** (WEB-V2.3 and earlier) pick the working draft with `pickLatestStudioDraft`, which ignores saved-design rows. They keep working and simply do not show saved designs.
- **Existing rows** are unaffected. No migration and no backfill.
- **Backend:** no change. Existing non-Studio create, update, and delete behaviour is untouched. The UI never calls `PUT` or `DELETE` on saved designs; a saved design is never overwritten.
- **Envelope versioning:** a future `fashionrise.saved_design.v2` would be shown as "damaged" by this client rather than misread.

---

## 2. Save as design: idempotency

- Each Save dialog session gets a `saveRequestId` (UUID). The snapshot is a deep copy taken **when the dialog opens**, so drawing afterwards never changes what is saved.
- **Success is shown only after the server acknowledges** a row whose snapshot fingerprint matches what was sent. The fingerprint is key-order independent, because PostgreSQL JSONB reorders keys.
- Retries in the same dialog reuse the same `saveRequestId`:

| Earlier attempt | What a retry does |
|---|---|
| Network error or 5xx (outcome uncertain) | Lists `/designs/my` and looks for that `saveRequestId` from this owner. If found, it reports success **without posting again**. If not found, it posts once. |
| Uncertain, and the lookup is also unreachable | **Does not post.** Shows an error; the user can try again later. |
| 4xx (for example, validation) | Final. Shown as an error and not treated as uncertain. |
| Offline (`navigator.onLine === false`) | No request. Honest error. No false success. |

- Double-clicking Save is guarded by an in-flight flag. The browser QA confirmed one row per double-click.
- The Studio working draft is not modified by saving.

**Residual risk (documented, not fixed):** if the original POST is still being processed on the server while the retry's lookup runs, the lookup can miss it and the retry posts a second copy. The window is small (the user must see the first failure and press Try again before the server finishes) and the result is a harmless duplicate, never data loss. Closing it fully needs server-side dedupe on `saveRequestId`. That is a backend change and is left for PM decision.

---

## 3. Export PNG

- Rendered from the **authoritative document** (`authoritativeDocRef`), not from a screenshot of the Konva stage.
- Output: 768×1024 PNG.
  - Cream paper `#F8F4F0`.
  - Built-in croquis reference, fit-contain, at 0.4 opacity when **Dim reference** is on.
  - Ink in its original colours and opacity.
  - Eraser applied with `destination-out` on the ink layer only, so the reference is never erased.
  - No UI chrome.
- A session-only custom reference is included when it can be loaded. If it cannot, the PNG is exported without it and the notice says so.
- Filename: `fashionrise-<title-slug or "sketch">-YYYY-MM-DD-HHMM.png`. Only `[a-z0-9-]`, max 48-character slug.
- Encoder failures (null, empty, or non-PNG blob) show an error, never a broken download. The temporary object URL is revoked in a `finally` block.
- No AI, no upload, no network request beyond the croquis image already used by Studio.

Examples from the simulated browser run (in `/opt/cursor/artifacts/web-v3a/`):

| File | Content |
|---|---|
| `export-desktop-two-strokes.png` | Female croquis at full opacity, two ink strokes |
| `export-desktop-dimmed.png` | Same with Dim reference on. Average reference darkness drops from 167 to 80. |
| `export-after-reopen.png` | Exported after reopening a saved design; matches the reopened content |
| `export-tablet-portrait.png` | Exported at 768×1024 viewport |

All four were checked to be true PNGs (signature `89 50 4E 47 0D 0A 1A 0A`), 768×1024, with cream paper and ink present.

---

## 4. My Designs

- Reached from the sidebar item **My Designs**, the More menu, and after a successful save.
- Route `/studio/designs` sits inside the same `/studio/*` page as Studio, so the editor and its save chain stay mounted while browsing. A pending autosave is never dropped by navigating.
- **Studio working draft** is shown on its own card: preview, model, stroke count, live save status, **Continue in Studio**.
- **Saved designs** are shown as a grid of cards (title, saved date, model, preview, **Open**), newest first, 24 at a time with **Show more**.
- States: loading (`role=status`), error with **Try again** (`role=alert`), empty, damaged rows (`role=note`), **Refresh**.
- Previews are rendered on the device at 240×320:
  - At most 2 renders at a time, cached by key.
  - Each object URL is revoked when its card unmounts and when the screen closes.
  - Thumbnails use a minimum ink width of 1.5 px so the default pencil-fine strokes stay visible. The full-size export keeps exact sizes.
- No likes, comments, sharing, Gallery, or publishing.
- Layout: the library scrolls inside the shell. Compact rules apply at short landscape and phone widths.

---

## 5. Reopen a saved design

Opening a saved design **replaces the content of the single working draft** with a copy of the snapshot. It uses the normal optimistic-concurrency write, so the saved design itself never changes and no second working draft is created.

1. **Fresh fetch and validation.** `GET /designs/{id}`, then the same strict parser: owner, private, saved-design envelope. Not found, foreign, or malformed rows stop here and nothing changes.
2. **Check the working copy:**

| Working copy state | What the user sees |
|---|---|
| Draft conflict dialog open | "Resolve your draft first", with **Go to Studio**. |
| Unsynced edits (local revision ahead of the server) | "Your Studio sketch is not saved yet", with **Retry save** or **Cancel**. Retry flushes the queued save, then asks again. |
| Synced, with strokes | "Open “title”?". It explains that the current sketch is replaced, the saved design stays unchanged, and how to keep the sketch (Save design first). Choices are **Replace and open** or **Cancel**. |
| Synced and empty | Opens directly. |

3. **Switch.** The write runs on the same serialized save chain as autosave, after any queued save:
   - The debounce timer is cleared.
   - Automatic saves are paused (`openingRef`) and the state is re-checked.
   - **Known draft id:** `PUT` with `expected_revision = last synced revision` and revision `max(local, synced) + 1` (unchanged OCC).
   - **No known draft id** (first-time / empty Studio): `persistStudioDraft({ createOnly: true })`. This may only create a new singleton draft or recover a lost response whose content matches the open. If another device’s draft appears at any point — including between the empty preflight list and the create — that draft is **preserved** and the open becomes an explicit conflict. It never adopts or overwrites a foreign draft solely to open a saved design.
4. **Outcome:**
   - **Success:** the Studio document, IndexedDB, and refs are updated together, and **undo history starts fresh**, so undo never spans designs. The status shows Saved and the app goes to Studio.
   - **409 whose server content is our snapshot:** treated as a recovered lost response and opened.
   - **409 with other content:** another device changed the draft. **Studio on this device is not updated.** The existing draft conflict dialog (Keep this device / Use cloud draft) is shown.
   - **Network / 5xx (uncertain):** Studio on this device is left unchanged, and the message says the server outcome **could not be confirmed** (it never claims “nothing was replaced”). **Try again** remains available; retry reuses the same safe OCC / createOnly path.
5. **Refresh** after opening restores the opened document from the server or IndexedDB with no conflict.

### Safety amendment (PM review follow-up)

Two issues from the Technical PM review are closed in this amendment:

1. **Empty-Studio cross-device race.** A preflight `listMyDesigns` alone was not atomic with create. Reopen with no known draft id now uses `createOnly`, and Studio create/reconcile on the backend returns **409** (instead of overwriting) when an existing working draft has different content at the same or higher revision. Autosave that already knows the draft id still uses `PUT` + OCC; autosave that discovers an existing draft without `createOnly` still adopts via OCC update.
2. **Uncertain reopen messaging.** Generic failures no longer say “Nothing was replaced,” because a server write may have committed before the response was lost.

---

## 6. Navigation

- Studio header: a visible **Save design** button. The label collapses to an icon at ≤520px and is 32px in compact landscape.
- **More** menu: Save as design…, Export PNG, My Designs, Clear canvas, Save now.
- Sidebar: **My Designs** is active. Home, Design Book, Discover, and My Looks stay disabled, and no future-tool placeholder was reactivated.
- Dialogs never stack:
  - The Save dialog does not render while a draft conflict or model-switch prompt is open.
  - Studio keyboard shortcuts and the Escape dock-close are suppressed while any `aria-modal` dialog is open.
- Dialogs label themselves (`aria-labelledby`), focus the primary action or title field, close with Escape when safe, and return focus on close.
- A bug found in browser QA is fixed: after a notice appeared, the More menu was drawn under the beta notice. The header now rises above the notice (z-index 45 vs 40) only while the menu is open.

---

## 7. Verification

### Automated

| Gate | Result |
|---|---|
| `npm test` (web-ui) | **Pass: 169 tests, 29 files.** |
| `npm run lint` | Pass. Same three pre-existing oxlint warnings, none new. |
| `npm run build` (`tsc -b` + Vite + PWA) | Pass. |
| Backend `pytest` focused suites (isolated `fashionrise_test` DB) | Studio concurrency + saved-design isolation: **15 / 15 pass.** |
| Backend full `pytest` | **103 passed, 1 failed.** The failure is `test_gpt6_luna_live_eval::test_cli_default_is_dry_run`, which also fails on clean `main`. It is unrelated. |

New test coverage:

| Area | Tests |
|---|---|
| Format isolation | Distinct envelope; ignored by working-draft selection; deep-copy snapshot; key-order-independent fingerprint. Backend: saved rows never reconcile; a nested Studio schema is ignored; singleton rules still hold after saved designs exist; owner privacy. |
| Save / idempotency | Matching acknowledgement only; lost response recovered without a second POST; uncertain retry finds the earlier row; posts once when the earlier attempt provably did not land; never posts blind; 4xx final; offline; mismatched acknowledgement; another account's request id ignored; dialog retry reuses the id; title validation; empty canvas blocked. |
| PNG export | Composition order; dim opacity; eraser on ink only; scaling; reference failure skip vs throw; missing 2D context; PNG blob validation; download plus guaranteed URL revoke; safe filenames; thumbnail-only minimum ink width. |
| Library | Sidebar entry without placeholders; same editor mounted across screens; draft shown separately; hostile titles as text; empty, error, and refresh states; preview concurrency, cache, release, and dispose. |
| Reopen | OCC replace after confirm; undo never spans designs; cancel is a no-op; empty draft opens directly; first-time users pass `createOnly`; draft created between preflight and persist is preserved (conflict, no overwrite); unsynced edits refused, then waits for the queued save; another device's change opens the conflict dialog; 409 with our content recovered; uncertain network messaging never claims the server was unchanged; lost-response-after-commit recovers on retry; malformed or foreign design refused; open conflict must be resolved first. |
| Persistence `createOnly` | Brand-new create; race between list and create; existing different draft refused; lost create with matching content recovered; autosave without `createOnly` still adopts via OCC update. |
| Backend create/reconcile | Same-content create is idempotent; different-content create at higher revision returns 409 and preserves the existing draft. |
| Layout | My Designs scroll and grid contract; short-landscape and phone rules; More menu above notices. |

### Local browser full flow (simulated)

**Simulated, not production.** Headless Chrome via Playwright, against local FastAPI on `127.0.0.1:8011` and an **isolated PostgreSQL database `fashionrise_v3a_qa`**. Two throwaway accounts (`qa_owner@example.com`, `qa_other@example.com`). `AI_WORKER_ENABLED=false`, empty OpenAI key. The production database was not used.

**Original full flow: 33 / 33 checks passed.** Safety amendment re-check (isolated DB, throwaway accounts): **16 / 16 passed** — backend create 409, brand-new open, empty-open race (device B preserved + conflict UI), uncertain PUT abort messaging, and safe retry after lost response.

**33 / 33 original checks covered:**

- **Save:**
  - Save creates exactly one row on double-click.
  - The working draft is untouched by saving.
  - The saved snapshot is independent of later edits.
- **Export:**
  - Real PNG (signature, 768×1024, cream paper, ink present) with a safe filename.
  - The dimmed export is still a valid PNG, with lighter reference pixels.
- **Library:**
  - A hostile title `Runway coat <b>v1</b>` renders as plain text.
  - Previews render.
- **Reopen:**
  - Reopen writes the working draft forward (revision 4 → 5).
  - Refresh restores the opened document with no conflict.
  - Export after reopen matches the reopened content.
- **Offline:** an offline save shows an honest error; going online and trying again saves exactly once.
- **Unsynced edits:** they block reopen with Retry save; after the retry, the confirm dialog appears.
- **Cross-device:**
  - A second device (tablet portrait) sees both saved designs.
  - A stale device that tries to reopen gets the conflict dialog instead of overwriting.
- **Layouts:**
  - Short landscape 1024×550: the Save design button and the paper are visible; My Designs scrolls to the Open buttons.
  - Phone 390 wide: no horizontal overflow.
- **Isolation:** the other account sees none of the owner's designs.
- **Final database check:** the owner still has exactly one Studio working draft.

Screenshots (`/opt/cursor/artifacts/web-v3a/`):

| # | File | Shows |
|---|---|---|
| 01 | `01-save-dialog-desktop.png` | Save as design dialog |
| 02 | `02-saved-notice-desktop.png` | Success notice after acknowledgement |
| 03 | `03-studio-export-notice-desktop.png` | Export notice |
| 04 | `04-my-designs-desktop.png` | My Designs, desktop (re-shot after the thumbnail ink fix, end-of-run data) |
| 05 | `05-open-confirm-desktop.png` | Replace-and-open confirmation |
| 06 | `06-reopened-studio-desktop.png` | Studio after reopening |
| 07 | `07-offline-save-error.png` | Honest offline save error |
| 08 | `08-open-blocked-unsynced.png` | Reopen refused while edits are unsynced |
| 09 | `09-my-designs-tablet-portrait.png` | My Designs, tablet portrait (re-shot) |
| 10 | `10-reopened-tablet-portrait.png` | Reopened on the second device |
| 11 | `11-stale-device-conflict.png` | Stale device gets the conflict dialog |
| 12 | `12-studio-short-landscape.png` | Studio at 1024×550 |
| 13 | `13-my-designs-short-landscape.png` | My Designs at 1024×550 (re-shot) |
| 14 | `14-my-designs-phone.png` | My Designs at 390 wide |
| 15 | `15-other-account-empty.png` | Second account sees nothing |

---

## 8. Known limitations

- **Idempotency race:** see §2. Duplicates are possible only if the original POST is still being processed when the retry's lookup runs. Server-side dedupe would close it (a backend change for PM decision).
- **Lost reopen response, then refresh:** if the reopen response is lost and the user refreshes instead of pressing Try again, the next load shows the normal conflict dialog (or restores the opened content if the write committed and this device never applied it). No data is lost; the user chooses explicitly. The in-dialog error now says the server outcome is unconfirmed rather than claiming the draft was unchanged.
- **Custom references are not saved.** Saved designs keep the model id only. Persistent uploads remain disabled.
- **No rename or delete** for saved designs yet.
- `/designs/my` returns full rows for every design. This is fine at family-beta scale; a paged, summary-only list would need a backend change.
- "Save now" can leave a redundant debounce timer running. This existed before WEB-V3A and is harmless.
- Local headless Chrome only. Physical-tablet acceptance on production has not happened yet.

---

## 9. Production acceptance tasks (after PM approval)

1. Before deploying, record the frontend revision **actually** live on the VPS. The WEB-V2.3 deploy log was not supplied, so do not assume it.
2. Deploy the merged SHA, then **restart FastAPI** so the create/reconcile 409 change is live. No PostgreSQL migration. Confirm the PWA service worker picks up the new frontend version.
3. On fashionrise.app, with a family-beta account:
   - Desktop: draw → Save design → My Designs → Open → Export PNG. Open the PNG and check paper, croquis, and ink.
   - Dim reference on → Export → reference visibly lighter.
   - Tablet (landscape with browser chrome, and portrait): Save, browse, Open, Export. Check the download works on iPadOS Safari and Android Chrome.
   - Cross-device: save on desktop, refresh My Designs on the tablet, open it there.
   - Two devices: open a design on one, then try to open on the stale one. Expect the conflict dialog, not an overwrite.
   - Offline: airplane mode → Save → honest error → back online → Try again → exactly one new card.
   - Refresh in Studio after an open restores the opened sketch.
4. Confirm a second account cannot see the first account's designs.
5. Confirm Magic, Generate with AI, uploads, registration, and Gallery remain disabled.
