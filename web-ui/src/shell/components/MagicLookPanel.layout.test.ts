import { describe, expect, it } from 'vitest'
import css from '@/shell/components/MagicLookPanel.module.css?raw'

/**
 * #180 — Mobile Try On Person modal must keep footer actions above Android chrome.
 * jsdom does not lay out CSS; pin the viewport/safe-area/sticky-footer contracts.
 */
function rule(source: string, selector: string): string {
  const start = source.indexOf(`${selector} {`)
  expect(start, `${selector} rule`).toBeGreaterThanOrEqual(0)
  return source.slice(start, source.indexOf('}', start))
}

describe('MagicLookPanel mobile viewport contract (#180)', () => {
  it('fixes the overlay to the visible viewport with safe-area padding', () => {
    const overlay = rule(css, '.overlay')
    expect(overlay).toContain('position: fixed')
    expect(overlay).toContain('env(safe-area-inset-top, 0px)')
    expect(overlay).toContain('env(safe-area-inset-bottom, 0px)')
    expect(overlay).toContain('overflow: hidden')
  })

  it('sizes the panel with svh/dvh so expanding browser chrome cannot bury actions', () => {
    const panel = rule(css, '.panel')
    expect(panel).toMatch(/100svh/)
    expect(panel).toMatch(/100dvh/)
    expect(panel).toContain('env(safe-area-inset-bottom, 0px)')
    expect(panel).toContain('min-height: 0')
    expect(panel).toContain('overflow: hidden')
  })

  it('scrolls body content while keeping a sticky/flex-safe footer region', () => {
    const body = rule(css, '.panelBody')
    expect(body).toContain('overflow-y: auto')
    expect(body).toContain('min-height: 0')
    expect(body).toContain('flex: 1 1 auto')

    const actions = rule(css, '.actions')
    expect(actions).toContain('flex-shrink: 0')
    expect(actions).toContain('position: sticky')
    expect(actions).toContain('bottom: 0')
    expect(actions).toContain('env(safe-area-inset-bottom, 0px)')
  })

  it('fits the look image inside the stage with contain (no head/hem CSS crop)', () => {
    const stage = rule(css, '.stage')
    // Definite height so absolute+contain has a real box (max-height alone still cropped).
    expect(stage).toMatch(/height:\s*min\(58dvh,\s*640px\)/)
    expect(stage).toContain('overflow: hidden')
    expect(stage).toContain('position: relative')
    // Absolute fill avoids iOS WKWebView flex+%-height crops of head/feet.
    expect(css).toMatch(/\.image,\s*\n\.sketchPreview \{[^}]*position: absolute/s)
    expect(css).toMatch(/\.image,\s*\n\.sketchPreview \{[^}]*inset: 0/s)
    expect(css).toMatch(/\.image,\s*\n\.sketchPreview \{[^}]*object-fit: contain/s)
    expect(css).not.toMatch(/\.image,\s*\n\.sketchPreview \{[^}]*object-fit: cover/s)
  })

  it('native shell look overlay fills edge-to-edge (no dead top band)', () => {
    expect(css).toContain('html.fr-native-shell')
    expect(css).toContain('place-items: stretch')
    // Overlay itself is unpadded; panel paints under the status bar.
    expect(css).toMatch(
      /html\.fr-native-shell\) \.overlay \{[^}]*padding:\s*0/s,
    )
    expect(css).toMatch(
      /html\.fr-native-shell\) \.panel \{[^}]*padding-top:\s*max\(10px,\s*env\(safe-area-inset-top/s,
    )
  })

  it('compacts at representative phone widths (320–430) without horizontal overflow', () => {
    expect(css).toContain('@media (max-width: 820px)')
    expect(css).toContain('@media (max-width: 430px)')
    expect(css).toContain('@media (max-height: 640px)')
    expect(css).toContain('@media (max-height: 480px)')
    const mobile = css.slice(css.indexOf('@media (max-width: 820px)'))
    expect(mobile).toContain('width: 100%')
    expect(mobile).toMatch(/100svh/)
    expect(mobile).toMatch(/100dvh/)
    expect(css).not.toMatch(/overflow-x:\s*scroll/)
  })

  it('preserves desktop panel max width and does not force full-bleed on wide screens', () => {
    const panel = rule(css, '.panel')
    expect(panel).toContain('width: min(920px, 100%)')
    expect(panel).toContain('900px')
  })
})
