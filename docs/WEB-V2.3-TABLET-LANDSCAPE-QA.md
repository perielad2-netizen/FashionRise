# WEB-V2.3 — tablet landscape fit and final Studio UI refinements

**Branch:** `cursor/web-v23-tablet-landscape-77c6`  
**Draft PR:** https://github.com/perielad2-netizen/FashionRise/pull/12  
**Base:** `main` at `9db1fa864ef9ddf622664be9be48c841f8a2a0ff` (deployed frontend)  
**Deployed backend:** `6df327ba9c40c2e28faaa04a9a97f97a2b092dd0` (unchanged here)  
**Not deployed.** Frontend-only change. No FastAPI, PostgreSQL, Nginx, Cloudflare, AI, upload, or registration change.

## Problem

WEB-V2.2 passed desktop acceptance, cross-device recovery, and two-tab conflict on fashionrise.app. On a physical tablet in landscape, browser tabs and the address bar leave a much shorter viewport than the screen. In that case:

- The paper was sized from width only (`width: min(100%, 420px)` with a 3:4 ratio), so it could not shrink to the available height.
- The workspace grid rows were `auto`, so the model library and tool rail could push the row taller than the viewport. The bottom of the paper was clipped.
- On desktop, 156px under the paper was reserved for a floating pencil window that duplicated the Settings brush controls.

Baseline measured on WEB-V2.2 (local Chrome, 100% zoom, offline notice showing):

| Viewport | Paper (CSS px) | Problem |
|---|---|---|
| 1024 × 550 | 346 × 461 at y 297 | Bottom edge at 758, 208px below the viewport |
| 1024 × 700 | 346 × 461 at y 297 | Bottom edge at 758, 58px below the viewport |
| 1180 × 600 | 277 × 370 | Floating brush window at y 609 and Generate with AI at y 689, both below the viewport |

The model cards also overlapped one another when the library column became short.

## Changes in this PR

### A. Short landscape and browser chrome

- `#root` uses `100dvh` where supported, so the app follows the visible viewport with tabs and the address bar showing. Installed PWA mode reports its own height the same way.
- The app shell pads by `env(safe-area-inset-*)` (the page already uses `viewport-fit=cover`).
- Shell, workspace, and paper-column grid rows are `minmax(0, 1fr)`, so panels scroll inside their own column instead of growing the page.
- The paper is a size container. Its width is `min(100cqw, max width, 75cqh)`, so the 3:4 sheet fits both width and height. The Konva stage still measures its host and scales design coordinates (768 × 1024), so strokes land where the pen touches.
- Compact rules apply only at `(min-width: 821px) and (max-height: 760px)`. They cover the global header (46px), workspace header, notice, dock, model library, tool rail (scrolls when taller than the paper column), brush sheet, and Settings spacing. Desktop at 1440 × 900 and 1920 × 1080 does not match this query.
- Model library rows are `max-content`, so cards no longer overlap when the column is short.
- Portrait keeps the WEB-V2.2 top-aligned paper. The fixed 420px paper minimum was removed, so the paper shrinks instead of running off-screen when the Models dock is open on a phone.

### B. Sidebar promo removed

The "Fashion is your superpower" card with the cropped croquis is gone. The navigation items, the active Create state, and the disabled Coming Soon items are unchanged. No replacement art.

### C. Generate with AI

The control sits in a sticky footer at the bottom of the scrolling Settings panel. It is one line, with the Soon label, and stays visibly unavailable. On short tablets it stays inside the visible panel while the sections above scroll. Clicking it still shows the existing Magic beta notice. No AI call.

### D. Desktop floating brush window removed

`DrawingWorkspace` no longer renders the floating pencil window or reserves space for it. On desktop the paper uses that room. Brush size, presets, and opacity stay in the right Settings panel.

At 1024px and below, the Brush dock opens the existing bottom sheet (`BrushControls`, formerly `FloatingBrushPanel`). The sheet is a dialog that closes with Done, the scrim, or Escape. At 1180px wide the Settings column is on screen, so brush controls are always reachable.

## Responsive matrix

Local headless Chrome on the dev server and on the production `vite preview` build. `devicePixelRatio` 1 and `visualViewport.scale` 1, so 100% zoom. These are browser simulations, not a physical tablet.

The paper sizes in this table are measured with no notice showing. The second column is with a beta notice open.

| Scenario | Viewport | Paper | Paper with notice | Brush controls | Result |
|---|---|---|---|---|---|
| Tablet landscape, short | 1024 × 550 | 260 × 346 | 227 × 302 | Dock sheet | Pass |
| Tablet landscape | 1180 × 600 | 324 × 432 | 291 × 388 | Settings column | Pass |
| Tablet landscape, taller | 1024 × 700 | 346 × 461 | 339 × 452 | Dock sheet | Pass |
| Tablet portrait | 768 × 1024 | 286 × 381 | 286 × 381 at y 320, same as WEB-V2.2 | Dock sheet | Pass |
| Mobile portrait | 390 × 844 | 286 × 381 | 286 × 381 at y 368, same as WEB-V2.2 | Dock sheet | Pass |
| Desktop | 1440 × 900 | 482 × 642 | 468 × 624 (WEB-V2.2: 345 × 460) | Settings column | Pass |
| Large desktop | 1920 × 1080 | 486 × 648 | 486 × 648 (WEB-V2.2: 386 × 514) | Settings column | Pass |
| Full-height sizes (installed PWA or no browser chrome) | 1180 × 820, 1024 × 768, 1366 × 1024 | 346 × 461, 342 × 456, 428 × 570 | — | — | Pass |

Checks at every viewport in the table:

- The paper is fully inside the viewport and keeps a 0.75 ratio.
- No horizontal or vertical document scrolling.
- Undo, Redo, Magic, Pencil, Eraser, and the save status are inside the viewport and are the topmost hit target.
- The Female model card is clickable (through the Models dock on phones).
- The Magic notice is visible, does not overlap the paper, and dismisses with Got it.
- The brush size and opacity sliders are reachable and clickable, through the sheet or the Settings column.
- Generate with AI fits on one line, stays inside the Settings panel, does not overlap the paper, and shows the beta notice.
- A mouse stroke, a pen stroke (CDP `pointerType: pen`), and a touch stroke (CDP touch events) each leave ink at the expected spot on the paper. A blank control spot stays empty.

Orientation and browser-chrome sequence, with one stroke drawn first:

768 × 1024 → 1024 × 550 → 1024 × 700 → 1024 × 550 → 1180 × 600 → 768 × 1024 → 1440 × 900

At every step the paper fits, the Konva stage is the same DOM node (no remount), the ink is still at the same relative position, and Undo stays enabled.

### Desktop comparison with WEB-V2.2

Pixel diff of 1440 × 900 and 1920 × 1080 screenshots against `9db1fa86`:

| Region | Changed |
|---|---|
| Global header | No |
| Workspace header and notice | No |
| Navigation items | No |
| Model library | No |
| Colors / Fabrics / Gradients / Layers column | No (only faint paper-shadow pixels, mean diff 0.3) |
| Settings sections | No |
| Sidebar bottom | Yes (promo removed) |
| Settings footer | Yes (Generate with AI on one line) |
| Paper area | Yes (floating brush window removed; paper larger) |

### Screenshots

Local only, under `/opt/cursor/artifacts/screenshots/web-v23/`:

- `compare-<viewport>.png`: WEB-V2.2 and WEB-V2.3 side by side at all seven sizes
- `after-<viewport>.png`: WEB-V2.3 default view
- `check-1024x550-drawn.png`, `check-1024x550-brush.png`, `check-1024x550-settings.png`, `check-1180x600-settings.png`
- `orientation-1024x550.png`, `models-390x844.png`

The local API stub returns 404 for `/api/v1/designs/my`, so screenshots show the existing “Working offline” notice or “Saved on this device”. That is a mock limitation, not a production cloud failure. Persistence code was not changed.

## Automated tests

- `src/pages/StudioPage.test.tsx`
  - Notice visibility and dismissal at 390 × 844, 768 × 1024, 1024 × 550, 1180 × 600, and 1440 × 900.
  - Desktop has no floating brush window, and Settings changes size and opacity.
  - At 1180 × 600 the brush sliders are in the Settings column.
  - At 1024 × 550 the Brush dock sheet changes size and opacity, and closes with Escape, Done, and the scrim.
  - Generate with AI stays labeled Soon and shows the notice at 1024 × 550, 1180 × 600, and 1440 × 900.
  - Orientation and browser-chrome changes keep the stroke, the brush size, and the same canvas node.
  - The sidebar promo is gone and the navigation controls remain.
- `src/shell/responsiveLayout.test.ts`: CSS contract for the root causes. jsdom does not lay out CSS, so this pins the constrained grid rows, the width-and-height paper sizing, `100dvh`, safe areas, the short-landscape query, the model-grid rows, and the sticky Generate footer.

## Still needed on a physical tablet

- Landscape in Safari and in Chrome with tabs and the address bar visible: paper fully visible, stylus strokes land under the pen tip, palm rejection unchanged.
- Rotate during a session: the drawing stays and keeps saving to the cloud.
- Show and hide the address bar (scroll gesture or tab switch) while drawing.
- Installed PWA in landscape and portrait.
- Brush dock sheet with touch: slide size and opacity, then close.
- Settings dock on a short screen: scroll to Generate with AI and tap it.
- Notch or rounded-corner devices: safe-area padding looks right in the installed PWA.

## Intentionally unchanged

- Magic and Generate with AI stay notice-only.
- Custom reference uploads stay session-only. Public registration stays off.
- Persistence (autosave, IndexedDB recovery, optimistic concurrency, conflict dialogs) was not modified.
- Brand assets are unchanged. Design-lab components are unchanged.
- Existing behavior: the brush size slider snaps to the nearest preset (Thin, Medium, Thick, Bold).
- Existing behavior: the login page scrolls on 550–600px-tall windows. It was not part of this milestone.
