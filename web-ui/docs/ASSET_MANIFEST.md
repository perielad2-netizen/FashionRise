# FashionRise WEB-V2.2 — UI asset manifest

Authoritative registry: `src/assets/uiAssets.ts`.

Derivations are produced by `web-ui/scripts/derive_brand_assets.py`. Originals are never overwritten.

| UI object | Registry key | Runtime path | Alpha check |
|-----------|--------------|--------------|-------------|
| Login.BrandLockup | `brand.login` | `/branding/fashion_rise_login.png` | True alpha. Crop of the approved logo: emblem plus FASHIONRISE wordmark. Tiny tagline and pill omitted. |
| GlobalHeader.Mark | `brand.mark` | `/branding/fashion_rise_mark.png` | True alpha. Approved monogram. |
| StudioHeader.BrandLogo | `brand.logo` | `/branding/fashion_rise_logo.png` | True alpha, hard mask. Full approved lockup, preserved. |
| Login emblem (unused in chrome, available) | `brand.emblem` | `/branding/fashion_rise_emblem.png` | True alpha. Emblem-only crop of the approved logo. |
| StudioHeader.Profile | `header.profile` | `/assets/ui/icons/fr_icon_profile.png` | True alpha |
| StudioHeader.Magic | `header.magic` | `/assets/ui/icons/fr_icon_magic.png` | True alpha |
| ModelPanel.FemaleCard | `model.female` | `/assets/ui/models/fr_model_female_card.png` | True alpha. Dark edge matte removed. |
| ModelPanel.MaleCard | `model.male` | `/assets/ui/models/fr_model_male_card.png` | True alpha. Low-alpha dark fringe removed. |
| ModelPanel.CustomCard | `model.custom` | `/assets/ui/models/fr_model_custom_card.png` | True alpha. Same card frame as the library. |
| ModelPanel.BlankCard | `model.blank` | `/assets/ui/models/fr_model_blank_card.png` | True alpha. Same card frame as the library. |
| ToolRail.Draw | `tool.draw` | `/assets/ui/icons/fr_icon_draw.png` | True alpha |
| ToolRail.Erase | `tool.erase` | `/assets/ui/icons/fr_icon_erase.png` | True alpha |
| ToolRail.Undo | `tool.undo` | `/assets/ui/icons/fr_icon_undo.png` | True alpha |
| ToolRail.Redo | `tool.redo` | `/assets/ui/icons/fr_icon_redo.png` | True alpha |
| ToolRail.Clear | `tool.clear` | `/assets/ui/icons/fr_icon_clear.png` | True alpha |
| StudioInspector.Reference | `inspector.reference` | `/assets/ui/icons/fr_icon_reference.png` | True alpha |
| StudioInspector.Magic | `inspector.magic` | `/assets/ui/icons/fr_icon_magic.png` | True alpha |
| DrawingCanvas.FemaleReference | `canvas.female` | `/models/female_model.png` | True alpha. Unchanged sketch reference. |
| DrawingCanvas.MaleReference | `canvas.male` | `/models/male_model_display.png` | True alpha. Unchanged sketch reference. |
| PWA / favicon tiles | (vite manifest) | `/icons/favicon-32.png`, `apple-touch-icon.png`, `icon-192.png`, `icon-512.png` | Opaque navy (`alpha 255` only). Mark composited inside the maskable safe zone. |

## Preserved sources

| File | Why it stays |
|------|----------------|
| `/branding/fashion_rise_logo.png` | Approved full lockup |
| `/branding/fashion_rise_mark.png` | Approved monogram |
| `/assets/ui/models/fr_model_female.png` | Library source, including the dark upper matte |
| `/assets/ui/models/fr_model_male.png` | Library source |
| `/assets/ui/models/fr_model_custom.png` | Library source |
| `/assets/ui/models/fr_model_blank.png` | Library source |
| `/models/male_model.png` | Opaque near-white male croquis source. Not used in UI. |

## Notes

- Alpha was measured with Pillow (`getchannel('A').getextrema()` and histograms), not assumed from file extension.
- The approved wordmark paints “FASHION” in navy. On the dark header that navy disappears, so the header uses the real monogram plus a cream/pink CSS wordmark. A recolored wordmark was not invented.
- Login places the cropped lockup on a cream plate so the navy wordmark stays readable, and does not repeat a second “FashionRise” title.
- The login crop drops the source tagline and “DESIGN YOUR DREAMS” pill because they become unreadably small in the card.
- Female library card: edge-connected dark matte cleared, then low-alpha near-black fringe removed. Figure ink kept. Original file kept.
- Male library source has no edge matte. Feet remain cropped in the original artwork. A replacement full-body male thumbnail would be required to show the feet; the current card is the best frame of the existing art.
- Custom and Blank keep their original rose-gold icons, reframed on a shared transparent 3:4 card. No new symbol was drawn.
- Canvas croquis were not replaced.
- `public/favicon.svg` is an unused purple mark from the Vite scaffold and is not linked. The live favicon is `icons/favicon-32.png`.
- `fr_icon_back.png` and `fr_icon_import.png` remain unmapped.
