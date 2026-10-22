import { existsSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  UI_ASSET_MANIFEST,
  UI_ASSETS,
  allProductionAssetPaths,
} from '@/assets/uiAssets'

const publicRoot = resolve(process.cwd(), 'public')

describe('UI_ASSETS registry', () => {
  it('exposes the required production keys', () => {
    expect(UI_ASSETS.brand.logo).toBe('/branding/fashion_rise_logo.png')
    expect(UI_ASSETS.brand.login).toBe('/branding/fashion_rise_login.png')
    expect(UI_ASSETS.brand.emblem).toBe('/branding/fashion_rise_emblem.png')
    expect(UI_ASSETS.brand.mark).toBe('/branding/fashion_rise_mark.png')
    expect(UI_ASSETS.header.profile).toMatch(/fr_icon_profile\.png$/)
    expect(UI_ASSETS.header.magic).toMatch(/fr_icon_magic\.png$/)
    expect(UI_ASSETS.model.female).toBe('/assets/ui/models/fr_model_female_card.png')
    expect(UI_ASSETS.model.male).toBe('/assets/ui/models/fr_model_male_card.png')
    expect(UI_ASSETS.model.custom).toBe('/assets/ui/models/fr_model_custom_card.png')
    expect(UI_ASSETS.model.blank).toBe('/assets/ui/models/fr_model_blank_card.png')
    expect(UI_ASSETS.tool.draw).toMatch(/fr_icon_draw\.png$/)
    expect(UI_ASSETS.tool.erase).toMatch(/fr_icon_erase\.png$/)
    expect(UI_ASSETS.tool.undo).toMatch(/fr_icon_undo\.png$/)
    expect(UI_ASSETS.tool.redo).toMatch(/fr_icon_redo\.png$/)
    expect(UI_ASSETS.tool.clear).toMatch(/fr_icon_clear\.png$/)
    expect(UI_ASSETS.inspector.reference).toMatch(/fr_icon_reference\.png$/)
    expect(UI_ASSETS.inspector.magic).toMatch(/fr_icon_magic\.png$/)
    expect(UI_ASSETS.canvas.female).toBe('/models/library/female-straight.png')
    expect(UI_ASSETS.canvas.male).toBe('/models/library/male-straight.png')
  })

  it('keeps canvas croquis separate from decorative model cards', () => {
    expect(UI_ASSETS.canvas.female).not.toBe(UI_ASSETS.model.female)
    expect(UI_ASSETS.canvas.male).not.toBe(UI_ASSETS.model.male)
    expect(UI_ASSETS.canvas.maleSource).toBe('/models/male_model.png')
  })

  it('ships WEB-V4D library croquis with transparency-ready PNGs', () => {
    const library = [
      'models/library/female-straight.png',
      'models/library/male-straight.png',
      'models/library/female-hand-hip.png',
      'models/library/male-step.png',
      'assets/ui/models/library/female-straight_card.png',
      'assets/ui/models/library/male-straight_card.png',
    ]
    for (const rel of library) {
      expect(existsSync(resolve(publicRoot, rel)), `missing ${rel}`).toBe(true)
    }
  })

  it('manifest covers every mapped UI object once', () => {
    const objects = UI_ASSET_MANIFEST.map((e) => e.uiObject)
    expect(new Set(objects).size).toBe(objects.length)
    expect(objects).toEqual(
      expect.arrayContaining([
        'Login.BrandLockup',
        'GlobalHeader.Mark',
        'StudioHeader.BrandLogo',
        'StudioHeader.Profile',
        'StudioHeader.Magic',
        'ModelPanel.FemaleCard',
        'ModelPanel.MaleCard',
        'ModelPanel.CustomCard',
        'ModelPanel.BlankCard',
        'ToolRail.Draw',
        'ToolRail.Erase',
        'ToolRail.Undo',
        'ToolRail.Redo',
        'ToolRail.Clear',
        'StudioInspector.Reference',
        'StudioInspector.Magic',
        'DrawingCanvas.FemaleReference',
        'DrawingCanvas.MaleReference',
      ]),
    )
  })

  it('every production asset path exists under public/', () => {
    for (const path of allProductionAssetPaths()) {
      expect(path.startsWith('/')).toBe(true)
      const disk = resolve(publicRoot, path.slice(1))
      expect(existsSync(disk), `missing ${path}`).toBe(true)
    }
    expect(existsSync(resolve(publicRoot, 'models/male_model.png'))).toBe(true)
    expect(existsSync(resolve(publicRoot, UI_ASSETS.model.femaleSource.slice(1)))).toBe(true)
    expect(existsSync(resolve(publicRoot, UI_ASSETS.model.maleSource.slice(1)))).toBe(true)
    expect(existsSync(resolve(publicRoot, UI_ASSETS.brand.logo.slice(1)))).toBe(true)
  })
})
