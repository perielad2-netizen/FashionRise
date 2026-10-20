import { describe, expect, it } from 'vitest'
import appShellCss from '@/shell/components/FashionRiseAppShell.module.css?raw'
import creatorCss from '@/shell/components/CreatorWorkspace.module.css?raw'
import drawingCss from '@/shell/components/DrawingWorkspace.module.css?raw'
import railCss from '@/shell/components/FloatingToolRail.module.css?raw'
import settingsCss from '@/shell/components/SettingsInspector.module.css?raw'
import modelCss from '@/shell/components/ModelLibraryPanel.module.css?raw'
import tokensCss from '@/shell/shellTokens.css?raw'
import globalCss from '@/styles/global.css?raw'

/**
 * jsdom does not lay out CSS, so these contracts pin the rules that keep the paper
 * inside short landscape viewports. Browser measurements live in
 * docs/WEB-V2.3-TABLET-LANDSCAPE-QA.md.
 */
const SHORT_LANDSCAPE = '@media (min-width: 821px) and (max-height: 760px)'

function rule(css: string, selector: string): string {
  const start = css.indexOf(`${selector} {`)
  expect(start, `${selector} rule`).toBeGreaterThanOrEqual(0)
  return css.slice(start, css.indexOf('}', start))
}

describe('WEB-V2.3 responsive layout contract', () => {
  it('constrains every grid row so panels cannot push the paper below the fold', () => {
    expect(rule(appShellCss, '.shell')).toContain('grid-template-rows: var(--fr-header-h) minmax(0, 1fr)')
    expect(rule(appShellCss, '.body')).toContain('grid-template-rows: minmax(0, 1fr)')
    expect(rule(creatorCss, '.body')).toContain('grid-template-rows: minmax(0, 1fr)')
    expect(rule(creatorCss, '.center')).toContain('grid-template-rows: minmax(0, 1fr)')
  })

  it('sizes the 3:4 paper from available width and height', () => {
    const frame = rule(drawingCss, '.canvasFrame')
    expect(frame).toContain('aspect-ratio: 768 / 1024')
    expect(frame).toContain('width: min(100cqw, var(--paper-max-w), 75cqh)')
    expect(rule(drawingCss, '.wrap')).toContain('container-type: size')
  })

  it('no longer reserves desktop space for a floating brush window', () => {
    expect(drawingCss).not.toContain('wrapWithBrush')
    expect(drawingCss).not.toContain('156px')
  })

  it('tracks the visible viewport and safe areas', () => {
    expect(globalCss).toContain('height: 100dvh')
    expect(rule(appShellCss, '.shell')).toContain('env(safe-area-inset-top, 0px)')
  })

  it('compacts chrome on short landscape viewports only', () => {
    for (const css of [tokensCss, appShellCss, creatorCss, drawingCss, railCss, settingsCss, modelCss]) {
      expect(css).toContain(SHORT_LANDSCAPE)
    }
    const compactRail = railCss.slice(railCss.indexOf(SHORT_LANDSCAPE))
    expect(compactRail).toContain('overflow-y: auto')
  })

  it('keeps model cards from collapsing onto each other when the library shrinks', () => {
    expect(rule(modelCss, '.grid')).toContain('grid-auto-rows: max-content')
  })

  it('pins Generate with AI inside the scrolling Settings panel on one line', () => {
    expect(rule(settingsCss, '.footer')).toContain('position: sticky')
    expect(rule(settingsCss, '.generateSoon')).toContain('white-space: nowrap')
  })
})

describe('WEB-V3A My Designs layout contract', () => {
  it('scrolls the library inside the shell instead of growing the page', async () => {
    const { default: libraryCss } = await import('@/shell/components/MyDesignsScreen.module.css?raw')
    expect(rule(libraryCss, '.screen')).toContain('min-height: 0')
    const scroll = rule(libraryCss, '.scroll')
    expect(scroll).toContain('min-height: 0')
    expect(scroll).toContain('overflow-y: auto')
    expect(rule(libraryCss, '.grid')).toContain('repeat(auto-fill, minmax(170px, 1fr))')
    expect(rule(libraryCss, '.paper')).toContain('aspect-ratio: 3 / 4')
  })

  it('compacts on short landscape and goes full-bleed in portrait phones', async () => {
    const { default: libraryCss } = await import('@/shell/components/MyDesignsScreen.module.css?raw')
    expect(libraryCss).toContain(SHORT_LANDSCAPE)
    expect(libraryCss).toContain('@media (max-width: 820px)')
  })
})
