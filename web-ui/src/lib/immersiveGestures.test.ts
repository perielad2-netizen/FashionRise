import { describe, expect, it } from 'vitest'
import { decidePointer } from '@/lib/pointerSession'
import {
  designToScreen,
  distance,
  midpoint,
  pinchPan,
  pinchScaleFactor,
  screenToDesign,
  zoomAt,
  fitPage,
} from '@/lib/viewportTransform'

/**
 * Gesture / transform safety for WEB-V4H immersive mode.
 * DrawingCanvas cancels drafts when a second touch begins; these tests lock the math + pointer rules.
 */
describe('immersive gesture safety helpers', () => {
  it('ignores a second pointer while a stroke session is active', () => {
    const session = { drawing: true, activePointerId: 1 }
    expect(
      decidePointer(session, {
        type: 'down',
        pointerId: 2,
        pointerType: 'touch',
        button: 0,
        buttons: 1,
      }),
    ).toBe('ignore')
  })

  it('requires a fresh begin after a cancelled stroke session', () => {
    const idle = { drawing: false, activePointerId: null }
    expect(
      decidePointer(idle, {
        type: 'move',
        pointerId: 1,
        pointerType: 'touch',
        button: 0,
        buttons: 1,
      }),
    ).toBe('ignore')
    expect(
      decidePointer(idle, {
        type: 'down',
        pointerId: 1,
        pointerType: 'touch',
        button: 0,
        buttons: 1,
      }),
    ).toBe('begin')
  })

  it('keeps pinch focal design point stable while scaling', () => {
    const viewport = { width: 1024, height: 768 }
    const before = fitPage(viewport)
    const a = { x: 400, y: 300 }
    const b = { x: 520, y: 360 }
    const mid = midpoint(a, b)
    const design = screenToDesign(mid.x, mid.y, before)
    const factor = pinchScaleFactor(distance(a, b), distance(a, b) * 1.35)
    const after = zoomAt(before, viewport, before.scale * factor, mid.x, mid.y)
    const again = screenToDesign(mid.x, mid.y, after)
    expect(again.x).toBeCloseTo(design.x, 5)
    expect(again.y).toBeCloseTo(design.y, 5)
  })

  it('maps fill/eyedropper hits under pan + zoom back to design space', () => {
    const viewport = { width: 900, height: 700 }
    const vp = zoomAt(fitPage(viewport), viewport, fitPage(viewport).scale * 2.5, 450, 350)
    // Sleeve-ish design point
    const sleeve = { x: 260, y: 420 }
    const screenX = sleeve.x * vp.scale + vp.panX
    const screenY = sleeve.y * vp.scale + vp.panY
    const hit = screenToDesign(screenX, screenY, vp)
    expect(hit.x).toBeCloseTo(sleeve.x, 6)
    expect(hit.y).toBeCloseTo(sleeve.y, 6)
  })

  it('combined pinch+pan keeps the garment point under the previous midpoint following to the new midpoint', () => {
    const box = { width: 1024, height: 768 }
    const before = fitPage(box)
    const prevA = { x: 380, y: 280 }
    const prevB = { x: 520, y: 360 }
    const prevMid = midpoint(prevA, prevB)
    const garment = screenToDesign(prevMid.x, prevMid.y, before)

    // Both distance and midpoint change in the same step.
    const nextA = { x: 300, y: 220 }
    const nextB = { x: 620, y: 420 }
    const nextMid = midpoint(nextA, nextB)
    const factor = pinchScaleFactor(distance(prevA, prevB), distance(nextA, nextB))
    const after = pinchPan(
      before,
      box,
      before.scale * factor,
      prevMid.x,
      prevMid.y,
      nextMid.x,
      nextMid.y,
    )

    const projected = designToScreen(garment.x, garment.y, after)
    expect(projected.x).toBeCloseTo(nextMid.x, 4)
    expect(projected.y).toBeCloseTo(nextMid.y, 4)

    // Wrong zoomAt(newMid)+panBy(delta) must NOT be considered correct here —
    // pinchPan is the regression lock for simultaneous scale + translate.
    const again = screenToDesign(nextMid.x, nextMid.y, after)
    expect(again.x).toBeCloseTo(garment.x, 4)
    expect(again.y).toBeCloseTo(garment.y, 4)
  })
})
