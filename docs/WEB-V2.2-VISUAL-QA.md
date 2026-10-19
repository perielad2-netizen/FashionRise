# WEB-V2.2 — visual and functional QA

**Branch:** `cursor/web-v22-premium-ui-77c6`  
**Draft PR:** https://github.com/perielad2-netizen/FashionRise/pull/11  
**Polish commit:** `ac06db12921bff8d60d1c031fae557d88a7b828a`  
**Notice fix:** one workspace-level beta notice, included in this draft and still awaiting PM review.  
**Base:** `main` at `6df327ba9c40c2e28faaa04a9a97f97a2b092dd0` (the protected production commit)  
**Not deployed.** Production `https://fashionrise.app` is unchanged.

This pass is a local browser check at device pixel ratio 1 and `visualViewport.scale === 1` (100% browser zoom). It is not production acceptance and not a physical tablet test.

## Functional audit

### Working

- Login validation, API login, redirect to Studio, session restore path, sign out
- Pencil and eraser, including B and E when focus is not in a field
- Brush size buttons, size slider, opacity slider, ink swatches, hex commit
- Undo, redo (buttons and Ctrl/Cmd+Z, Ctrl/Cmd+Shift+Z, Ctrl/Cmd+Y)
- Clear canvas from the More menu
- Female, male, and blank model selection
- Model-switch confirmation when ink exists (Keep strokes / Clear strokes / Cancel)
- Custom file picker (session preview only; cloud payload still strips the reference)
- Dim reference
- Autosave status, Retry, Save now, conflict dialogs (unchanged WEB-V2.1C code)
- Hamburger navigation and scrim
- Model filters All / Female / Male
- Responsive dock: Models, Brush panel, Materials, Settings
- Brush sheet Done and scrim on viewports ≤1024px
- Desktop brush controls sit under the paper instead of covering it

### Fixed in this milestone

| Control | Was | Now |
|---------|-----|-----|
| Shortcuts B, E, Ctrl/Cmd+Z, Ctrl/Cmd+Shift+Z | Advertised, not wired | Wired, ignored while typing |
| Magic and Generate with AI | Primary pink actions | Dashed “Soon” controls that still explain the beta limit |
| Header Settings | Looked like a live settings button | Dashed, labeled “coming later”, still explains on click |
| Back | Looked like navigation | Muted, labeled “Home, coming later” |
| My Gallery | Selectable tab with an empty note | Disabled, labeled Soon |
| Canvas size | Fake dropdown | Static “768 × 1024” |
| Background chip | Fake input | Text “Cream paper” |
| Color field and hue bar | Looked draggable, did nothing | Replaced by the current-ink chip; swatches and hex remain |
| Female library thumbnail | Opaque dark matte around the head | Edge matte removed; original file kept |
| Login logo | 72px cover crop plus a second wordmark | Approved emblem and wordmark on a cream plate, no second title |
| Header wordmark | Wide tracked pink capitals | Compact cream “Fashion” and pink “Rise” beside the real monogram |
| Narrow tool rail | Undo/redo clipped off a 390px screen | Rail scrolls; header undo/redo stay visible |
| App icons | Opaque navy tiles without the monogram | Opaque navy tiles with the approved mark |
| Magic, Back, and header Settings notices | Rendered inside Settings, which is hidden at 1024px and below | One dismissible notice under the workspace title; Settings stays closed |

### Intentionally disabled

- Home, Design Book, Discover, My Looks
- Pen, Brush, Eyedropper, Select, Shape, Type, Ruler, Layers on the tool rail
- Help, pressure toggle, eyedropper, fabrics, gradients, layer editing
- Zoom, fit, and fullscreen
- Pose A / Pose B / Pose E cards (Unavailable)
- Magic / Generate with AI (notice only, no API)
- Persistent custom uploads and public registration

### Deferred

- A full color picker
- Home and gallery destinations
- Paid Magic
- Owner-private uploads
- A full-body male thumbnail (source art cuts the feet)
- A dark-header version of the approved navy wordmark (not recolored)
- Physical tablet and production-browser acceptance

## Responsive check (100% zoom)

Local Vite at `http://127.0.0.1:5180`, signed in against a local stub. Canvas stayed reachable. No document-level horizontal overflow at these sizes.

| Viewport | Result |
|----------|--------|
| 1440 × 900 | Login plate and Studio grid usable. Model confirm and Magic notice open on top of the workspace. Brush panel is below the paper. |
| 1920 × 1080 | Same desktop grid with more margin. Branding stays header-sized. |
| 1024 × 768 | Settings become an overlay. Dock appears. Brush opens as a bottom sheet. Models stay in the left column. |
| 768 × 1024 | Models, brush, materials, and settings are dock overlays. Default view keeps the paper clear. |
| 390 × 844 | Same overlay model. Tool rail scrolls to the later tools. Canvas remains on screen. |
| 1440 × 900 at CSS zoom 1.5 | `visualViewport.scale` stayed 1 (this is not browser zoom). The paper compresses because the panels and brush reserve space. Treated as zoom pressure, not the 100% layout defect. |

## Notice visibility

Magic, Back, header Settings, and studio messages render as one dismissible status under the workspace title. They are not inside `SettingsInspector`, which is hidden at 1024px and below until its dock opens. A new action replaces the previous notice. Dismiss clears it. The bar stays in the header stack, above the dock, so it does not cover the paper or the brush controls.

Component regression in `StudioPage.test.tsx` clicks Magic, header Settings, and Back at 390, 768, and 1440. Each notice is visible, outside the settings inspector, and dismisses. Opening the Settings dock is not required.

## Evidence limits

- Screenshots are from headless Chrome on this agent, not from `https://fashionrise.app` and not from a physical tablet.
- The local API stub returned 404 for `/api/v1/designs/my`. Studio then showed the existing local-only / offline status. Persistence code was not changed. This does not re-prove cloud save.
- Drawing, model-switch confirmation, Magic notice, and the brush sheet were exercised in that browser.

## Asset derivation

See `web-ui/docs/ASSET_MANIFEST.md`. Script: `web-ui/scripts/derive_brand_assets.py`.
