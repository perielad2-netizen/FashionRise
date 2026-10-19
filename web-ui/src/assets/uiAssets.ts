/**
 * FashionRise WEB-1 — single authoritative UI asset registry.
 * Components must read paths from here rather than hardcoding URLs.
 *
 * Public paths under `web-ui/public/` resolve in Vite dev and production.
 */

export const UI_ASSETS = {
  brand: {
    /** Full brand lockup (cream bg made transparent for navy shell). */
    logo: '/branding/fashion_rise_logo.png',
    /** Optional compact emblem (R mark) — available but not required by mapping. */
    mark: '/branding/fashion_rise_mark.png',
  },
  header: {
    profile: '/assets/ui/icons/fr_icon_profile.png',
    magic: '/assets/ui/icons/fr_icon_magic.png',
  },
  model: {
    female: '/assets/ui/models/fr_model_female.png',
    male: '/assets/ui/models/fr_model_male.png',
    custom: '/assets/ui/models/fr_model_custom.png',
    blank: '/assets/ui/models/fr_model_blank.png',
  },
  tool: {
    draw: '/assets/ui/icons/fr_icon_draw.png',
    erase: '/assets/ui/icons/fr_icon_erase.png',
    undo: '/assets/ui/icons/fr_icon_undo.png',
    redo: '/assets/ui/icons/fr_icon_redo.png',
    clear: '/assets/ui/icons/fr_icon_clear.png',
  },
  inspector: {
    reference: '/assets/ui/icons/fr_icon_reference.png',
    magic: '/assets/ui/icons/fr_icon_magic.png',
  },
  canvas: {
    /**
     * Drawing-canvas croquis (NOT the decorative model-card art).
     * Female source already has a true alpha channel.
     */
    female: '/models/female_model.png',
    /**
     * Runtime male reference is a cleaned display asset.
     * Original opaque source preserved at `/models/male_model.png`.
     */
    male: '/models/male_model_display.png',
    /** Original male source (baked light background) — do not use in UI. */
    maleSource: '/models/male_model.png',
  },
} as const

export type UiAssetGroup = keyof typeof UI_ASSETS

/** Flat production map used by manifest docs and completeness tests. */
export const UI_ASSET_MANIFEST = [
  { uiObject: 'StudioHeader.BrandLogo', key: 'brand.logo', path: UI_ASSETS.brand.logo },
  { uiObject: 'StudioHeader.Profile', key: 'header.profile', path: UI_ASSETS.header.profile },
  { uiObject: 'StudioHeader.Magic', key: 'header.magic', path: UI_ASSETS.header.magic },
  { uiObject: 'ModelPanel.FemaleCard', key: 'model.female', path: UI_ASSETS.model.female },
  { uiObject: 'ModelPanel.MaleCard', key: 'model.male', path: UI_ASSETS.model.male },
  { uiObject: 'ModelPanel.CustomCard', key: 'model.custom', path: UI_ASSETS.model.custom },
  { uiObject: 'ModelPanel.BlankCard', key: 'model.blank', path: UI_ASSETS.model.blank },
  { uiObject: 'ToolRail.Draw', key: 'tool.draw', path: UI_ASSETS.tool.draw },
  { uiObject: 'ToolRail.Erase', key: 'tool.erase', path: UI_ASSETS.tool.erase },
  { uiObject: 'ToolRail.Undo', key: 'tool.undo', path: UI_ASSETS.tool.undo },
  { uiObject: 'ToolRail.Redo', key: 'tool.redo', path: UI_ASSETS.tool.redo },
  { uiObject: 'ToolRail.Clear', key: 'tool.clear', path: UI_ASSETS.tool.clear },
  { uiObject: 'StudioInspector.Reference', key: 'inspector.reference', path: UI_ASSETS.inspector.reference },
  { uiObject: 'StudioInspector.Magic', key: 'inspector.magic', path: UI_ASSETS.inspector.magic },
  {
    uiObject: 'DrawingCanvas.FemaleReference',
    key: 'canvas.female',
    path: UI_ASSETS.canvas.female,
  },
  {
    uiObject: 'DrawingCanvas.MaleReference',
    key: 'canvas.male',
    path: UI_ASSETS.canvas.male,
  },
] as const

export function allProductionAssetPaths(): string[] {
  return UI_ASSET_MANIFEST.map((entry) => entry.path)
}
