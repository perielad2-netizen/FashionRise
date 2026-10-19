# WEB-V2 visual & functional QA

**Date:** 2026-10-19  
**Branch:** `cursor/web-ui-reboot`  
**Route:** production `/studio` (approved shell + real Konva engine)

## Screenshots

| Viewport | Path |
|----------|------|
| 1536×1024 | `/opt/cursor/artifacts/screenshots/studio-webv2-1536x1024.png` |
| 1440×900 | `/opt/cursor/artifacts/screenshots/studio-webv2-1440x900.png` |
| 1024×768 | `/opt/cursor/artifacts/screenshots/studio-webv2-1024x768.png` |
| 768×1024 | `/opt/cursor/artifacts/screenshots/studio-webv2-768x1024.png` |
| 390×844 | `/opt/cursor/artifacts/screenshots/studio-webv2-390x844.png` |
| 390×844 brush sheet | `/opt/cursor/artifacts/screenshots/studio-webv2-390x844-brush-sheet.png` |
| Functional drawing | `/opt/cursor/artifacts/screenshots/studio-webv2-functional-drawing.png` |
| Side-by-side vs design-lab | `/opt/cursor/artifacts/screenshots/webv2-studio-vs-designlab-1536x1024.png` |

## Side-by-side differences (studio vs `/_design/studio`)

| Topic | Status |
|-------|--------|
| Overall shell composition | Strong match |
| Prototype banner | Removed from `/studio` (kept on design-lab) |
| Save status | Studio shows **Unsaved session**; design-lab may still show Auto Save chrome |
| Model library | Studio connects Female/Male/Custom/Blank; placeholders marked Unavailable |
| Canvas | Real Konva croquis + ink (not static sketch artwork) |
| Tool rail | Pencil/Eraser/Undo/Redo live; future tools disabled |
| Brush card | Live size/opacity; mobile uses **Brush panel** sheet |
| Colors | Live swatches + hex; fabrics/gradients/layers unavailable |
| Settings | Live brush/dim; canvas size fixed 768×1024; pressure toggle disabled |
| Magic / Generate with AI | Notice only; **0** paid AI requests observed |

## Functional checks performed

Login (mocked session) → Studio · Female/Male/Blank · pencil hold-draw · release+move · eraser · undo/redo · clear+undo · color · dim · Magic notice · Sign out → `/login` · mobile brush sheet.

## Remaining gaps vs mock photography

Photographic model catalog and finished hat/dress sketch artwork remain unavailable (same as WEB-V1).
