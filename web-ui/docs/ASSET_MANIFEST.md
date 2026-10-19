# FashionRise WEB-1 — UI asset manifest

Authoritative registry: `src/assets/uiAssets.ts`.

| UI object | Registry key | Runtime path |
|-----------|--------------|--------------|
| StudioHeader.BrandLogo | `brand.logo` | `/branding/fashion_rise_logo.png` |
| StudioHeader.Profile | `header.profile` | `/assets/ui/icons/fr_icon_profile.png` |
| StudioHeader.Magic | `header.magic` | `/assets/ui/icons/fr_icon_magic.png` |
| ModelPanel.FemaleCard | `model.female` | `/assets/ui/models/fr_model_female.png` |
| ModelPanel.MaleCard | `model.male` | `/assets/ui/models/fr_model_male.png` |
| ModelPanel.CustomCard | `model.custom` | `/assets/ui/models/fr_model_custom.png` |
| ModelPanel.BlankCard | `model.blank` | `/assets/ui/models/fr_model_blank.png` |
| ToolRail.Draw | `tool.draw` | `/assets/ui/icons/fr_icon_draw.png` |
| ToolRail.Erase | `tool.erase` | `/assets/ui/icons/fr_icon_erase.png` |
| ToolRail.Undo | `tool.undo` | `/assets/ui/icons/fr_icon_undo.png` |
| ToolRail.Redo | `tool.redo` | `/assets/ui/icons/fr_icon_redo.png` |
| ToolRail.Clear | `tool.clear` | `/assets/ui/icons/fr_icon_clear.png` |
| StudioInspector.Reference | `inspector.reference` | `/assets/ui/icons/fr_icon_reference.png` |
| StudioInspector.Magic | `inspector.magic` | `/assets/ui/icons/fr_icon_magic.png` |
| DrawingCanvas.FemaleReference | `canvas.female` | `/models/female_model.png` |
| DrawingCanvas.MaleReference | `canvas.male` | `/models/male_model_display.png` |

## Notes

- Model-card art (`fr_model_*`) and canvas croquis (`/models/*`) are **different** assets.
- Male croquis source `/models/male_model.png` had a baked near-white opaque background (not true alpha). Runtime uses cleaned `male_model_display.png`; original source is preserved.
- Tool icons are transparent PNGs (glyph only). Button chrome / active / disabled states are CSS.
- `fr_icon_back.png` and `fr_icon_import.png` are retained in `public/assets/ui/icons/` but are not mapped into WEB-1 chrome.
- Compact brand mark `/branding/fashion_rise_mark.png` is available; the header uses the full logo path from the mapping.
