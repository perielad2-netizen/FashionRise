import { describe, expect, it } from 'vitest'
import { DESIGN_HEIGHT, DESIGN_WIDTH } from '@/lib/strokes'
import {
  absoluteHundredPercentScale,
  clampPan,
  clampScale,
  designToScreen,
  fitPage,
  fitPageScale,
  fitWidth,
  fitWidthScale,
  hundredPercent,
  pinchScaleFactor,
  safeViewport,
  scaleLimits,
  screenToDesign,
  zoomAt,
  zoomPercent,
} from '@/lib/viewportTransform'

const tablet = { width: 768, height: 900 }
const landscape = { width: 1180, height: 700 }

describe('viewportTransform', () => {
  it('computes Fit Page so the full 3:4 page fits inside the viewport', () => {
    const s = fitPageScale(tablet)
    expect(s).toBeCloseTo(Math.min(tablet.width / DESIGN_WIDTH, tablet.height / DESIGN_HEIGHT), 8)
    const vp = fitPage(tablet)
    expect(vp.scale).toBeCloseTo(s, 8)
    expect(DESIGN_WIDTH * vp.scale).toBeLessThanOrEqual(tablet.width + 0.01)
    expect(DESIGN_HEIGHT * vp.scale).toBeLessThanOrEqual(tablet.height + 0.01)
  })

  it('computes Fit Width using nearly all horizontal space', () => {
    const s = fitWidthScale(tablet)
    expect(s).toBeCloseTo(tablet.width / DESIGN_WIDTH, 8)
    const vp = fitWidth(tablet)
    expect(vp.scale).toBeCloseTo(s, 8)
    expect(Math.abs(vp.panX)).toBeLessThan(1)
    // Taller than viewport → top-aligned for garment reachability.
    expect(vp.panY).toBe(0)
  })

  it('defines 100% as one design pixel per CSS pixel', () => {
    expect(absoluteHundredPercentScale()).toBe(1)
    const vp = hundredPercent(tablet)
    expect(vp.scale).toBe(1)
  })

  it('keeps Fit Width and 100% inside scale limits', () => {
    const { min, max } = scaleLimits(tablet)
    expect(fitWidthScale(tablet)).toBeLessThanOrEqual(max + 1e-9)
    expect(1).toBeLessThanOrEqual(max + 1e-9)
    expect(fitPageScale(tablet) * 0.5).toBeGreaterThanOrEqual(min - 1e-9)
  })

  it('clamps invalid / NaN scales to Fit Page', () => {
    expect(clampScale(Number.NaN, tablet)).toBeCloseTo(fitPageScale(tablet), 8)
    expect(clampScale(-2, tablet)).toBeCloseTo(fitPageScale(tablet), 8)
    expect(clampScale(0, tablet)).toBeCloseTo(fitPageScale(tablet), 8)
  })

  it('round-trips screen ↔ design coordinates', () => {
    const vp = fitPage(landscape)
    const samples = [
      [0, 0],
      [DESIGN_WIDTH / 2, DESIGN_HEIGHT / 2],
      [100, 200],
      [700, 900],
    ] as const
    for (const [dx, dy] of samples) {
      const screen = designToScreen(dx, dy, vp)
      const back = screenToDesign(screen.x, screen.y, vp)
      expect(back.x).toBeCloseTo(dx, 8)
      expect(back.y).toBeCloseTo(dy, 8)
    }
  })

  it('preserves the design point under the zoom anchor', () => {
    const before = fitPage(tablet)
    const anchor = designToScreen(220, 180, before) // neckline-ish
    const after = zoomAt(before, tablet, before.scale * 2.2, anchor.x, anchor.y)
    const designAfter = screenToDesign(anchor.x, anchor.y, after)
    expect(designAfter.x).toBeCloseTo(220, 5)
    expect(designAfter.y).toBeCloseTo(180, 5)
    expect(after.scale).toBeGreaterThan(before.scale)
  })

  it('keeps pinch focal stability via zoomAt midpoints', () => {
    const before = fitWidth(landscape)
    const mid = { x: landscape.width / 2, y: landscape.height / 2 }
    const designBefore = screenToDesign(mid.x, mid.y, before)
    const factor = pinchScaleFactor(100, 150)
    expect(factor).toBeCloseTo(1.5, 8)
    const after = zoomAt(before, landscape, before.scale * factor, mid.x, mid.y)
    const designAfter = screenToDesign(mid.x, mid.y, after)
    expect(designAfter.x).toBeCloseTo(designBefore.x, 5)
    expect(designAfter.y).toBeCloseTo(designBefore.y, 5)
  })

  it('clamps pan so the page cannot be lost off-screen', () => {
    const vp = fitWidth(tablet)
    const lost = clampPan({ scale: vp.scale, panX: -20000, panY: 20000 }, tablet)
    const corner = designToScreen(0, 0, lost)
    // Some part of the page remains near the viewport.
    expect(corner.x).toBeGreaterThan(-DESIGN_WIDTH * lost.scale)
    expect(corner.y).toBeLessThan(tablet.height + DESIGN_HEIGHT * lost.scale)
  })

  it('guards zero / invalid viewport sizes', () => {
    const safe = safeViewport({ width: 0, height: -3 })
    expect(safe.width).toBe(DESIGN_WIDTH)
    expect(safe.height).toBe(DESIGN_HEIGHT)
    expect(fitPageScale(safe)).toBeGreaterThan(0)
  })

  it('reports zoom percent from absolute scale', () => {
    expect(zoomPercent(1)).toBe(100)
    expect(zoomPercent(2.25)).toBe(225)
  })

  it('re-centers after viewport resize / orientation change', () => {
    const portrait = fitPage({ width: 768, height: 1024 })
    const after = fitPage({ width: 1024, height: 768 })
    expect(after.scale).not.toBeCloseTo(portrait.scale, 3)
    expect(DESIGN_WIDTH * after.scale).toBeLessThanOrEqual(1024 + 0.01)
  })
})
