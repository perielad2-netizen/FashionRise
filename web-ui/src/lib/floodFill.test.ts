import { describe, expect, it } from 'vitest'
import {
  DEFAULT_GAP_CLOSE_PX,
  FILL_UNDER_INK_PX,
  dilateMask,
  expandVisitedUnderBarrier,
  floodFillAgainstBarrier,
} from '@/lib/floodFill'
import {
  PAPER_HEIGHT,
  PAPER_WIDTH,
  designToPaperIndex,
  designToPaperX,
  designToPaperY,
} from '@/lib/paperBounds'
import { solidStyle } from '@/lib/fills'

function emptyBarrier(): Uint8Array {
  return new Uint8Array(PAPER_WIDTH * PAPER_HEIGHT)
}

function mark(barrier: Uint8Array, x: number, y: number): void {
  const i = designToPaperIndex(x, y)
  if (i >= 0) barrier[i] = 1
}

/** Closed rectangle ring so the interior is fillable and does not touch the paper edge. */
function closedRectBarrier(x0: number, y0: number, x1: number, y1: number): Uint8Array {
  const barrier = emptyBarrier()
  for (let x = x0; x <= x1; x += 1) {
    mark(barrier, x, y0)
    mark(barrier, x, y1)
  }
  for (let y = y0; y <= y1; y += 1) {
    mark(barrier, x0, y)
    mark(barrier, x1, y)
  }
  return barrier
}

describe('floodFillAgainstBarrier', () => {
  it('fills a closed bodice-sized region with the selected solid color', () => {
    const barrier = closedRectBarrier(200, 200, 400, 420)
    const result = floodFillAgainstBarrier({
      barrier,
      x: 300,
      y: 300,
      style: solidStyle('#B91C1C'),
    })
    expect(result.ok).toBe(true)
    if (!result.ok) return
    expect(result.fill.style).toEqual({ kind: 'solid', color: '#B91C1C' })
    expect(result.fill.contour.length).toBeGreaterThanOrEqual(6)
    // Contour may sit on the outline ring (under-ink expand) but must not escape the box.
    for (let i = 0; i < result.fill.contour.length; i += 2) {
      expect(result.fill.contour[i]!).toBeGreaterThanOrEqual(200)
      expect(result.fill.contour[i]!).toBeLessThanOrEqual(400)
      expect(result.fill.contour[i + 1]!).toBeGreaterThanOrEqual(200)
      expect(result.fill.contour[i + 1]!).toBeLessThanOrEqual(420)
    }
  })

  it('tucks the fill contour under the outline so gap-close dilate does not leave a white margin', () => {
    // Visible ink = 1px ring; flood barrier = dilated (same as Studio gap-close).
    const visible = closedRectBarrier(200, 200, 400, 420)
    const barrier = dilateMask(visible, DEFAULT_GAP_CLOSE_PX)
    const result = floodFillAgainstBarrier({
      barrier,
      visibleInk: visible,
      x: 300,
      y: 300,
      style: solidStyle('#1D4ED8'),
    })
    expect(result.ok).toBe(true)
    if (!result.ok) return
    // Contour must reach the visible ink ring (not stop inset by dilate).
    let touchesVisibleRing = false
    for (let i = 0; i < result.fill.contour.length; i += 2) {
      const x = Math.round(result.fill.contour[i]!)
      const y = Math.round(result.fill.contour[i + 1]!)
      const idx = designToPaperIndex(x, y)
      if (idx >= 0 && visible[idx]) touchesVisibleRing = true
      // Also accept contour centres within 1px of the ring (trace sits on edge).
      for (const [dx, dy] of [
        [0, 0],
        [1, 0],
        [-1, 0],
        [0, 1],
        [0, -1],
      ] as const) {
        const j = designToPaperIndex(x + dx, y + dy)
        if (j >= 0 && visible[j]) touchesVisibleRing = true
      }
    }
    expect(touchesVisibleRing).toBe(true)
    expect(FILL_UNDER_INK_PX).toBeGreaterThan(DEFAULT_GAP_CLOSE_PX)
  })

  it('expandVisitedUnderBarrier only grows into barrier pixels', () => {
    const visited = new Uint8Array(PAPER_WIDTH * PAPER_HEIGHT)
    const barrier = closedRectBarrier(100, 100, 140, 140)
    // Interior immediately inside the ring so radius-2 expand reaches the ink.
    for (let y = 101; y <= 139; y += 1) {
      for (let x = 101; x <= 139; x += 1) {
        visited[designToPaperIndex(x, y)] = 1
      }
    }
    expandVisitedUnderBarrier(visited, barrier, 2, {
      minX: designToPaperX(101),
      minY: designToPaperY(101),
      maxX: designToPaperX(139),
      maxY: designToPaperY(139),
    })
    // Ring pixels should now be visited; exterior just outside the ring must stay empty.
    expect(visited[designToPaperIndex(100, 120)]).toBe(1)
    expect(visited[designToPaperIndex(99, 120)]).toBe(0)
  })

  it('fills bodice and skirt regions independently', () => {
    const barrier = emptyBarrier()
    // Outer dress silhouette
    for (let x = 250; x <= 450; x += 1) {
      mark(barrier, x, 180)
      mark(barrier, x, 700)
    }
    for (let y = 180; y <= 700; y += 1) {
      mark(barrier, 250, y)
      mark(barrier, 450, y)
    }
    // Waist seam separating bodice / skirt
    for (let x = 250; x <= 450; x += 1) {
      mark(barrier, x, 380)
    }

    const bodice = floodFillAgainstBarrier({
      barrier,
      x: 350,
      y: 280,
      style: solidStyle('#B91C1C'),
    })
    const skirt = floodFillAgainstBarrier({
      barrier,
      x: 350,
      y: 520,
      style: solidStyle('#1D4ED8'),
    })
    expect(bodice.ok).toBe(true)
    expect(skirt.ok).toBe(true)
    if (!bodice.ok || !skirt.ok) return
    expect(bodice.fill.style).toEqual({ kind: 'solid', color: '#B91C1C' })
    expect(skirt.fill.style).toEqual({ kind: 'solid', color: '#1D4ED8' })
    const bodiceMaxY = Math.max(...bodice.fill.contour.filter((_, i) => i % 2 === 1))
    const skirtMinY = Math.min(...skirt.fill.contour.filter((_, i) => i % 2 === 1))
    // Under-ink expand may tuck both contours onto the shared waist seam pixels.
    expect(bodiceMaxY).toBeLessThanOrEqual(380 + FILL_UNDER_INK_PX)
    expect(skirtMinY).toBeGreaterThanOrEqual(380 - FILL_UNDER_INK_PX)
    expect(bodiceMaxY).toBeLessThan(skirtMinY + FILL_UNDER_INK_PX + 2)
  })

  it('rejects open outlines that leak to the paper edge', () => {
    const barrier = emptyBarrier()
    // Three sides only — open at the top.
    for (let y = 200; y <= 500; y += 1) {
      mark(barrier, 200, y)
      mark(barrier, 400, y)
    }
    for (let x = 200; x <= 400; x += 1) {
      mark(barrier, x, 500)
    }
    const result = floodFillAgainstBarrier({
      barrier,
      x: 300,
      y: 350,
      style: solidStyle('#111111'),
    })
    expect(result.ok).toBe(false)
    if (result.ok) return
    expect(result.reason).toBe('open_outline')
    expect(result.message).toMatch(/close the shape/i)
    expect(result.message.toLowerCase()).not.toContain('dress')
  })

  it('rejects taps on the barrier and outside the extended paper', () => {
    const barrier = closedRectBarrier(100, 100, 200, 200)
    expect(
      floodFillAgainstBarrier({
        barrier,
        x: 100,
        y: 150,
        style: solidStyle('#111111'),
      }).ok,
    ).toBe(false)
    // Negative design coords inside the paper margins are valid; go past the origin.
    expect(
      floodFillAgainstBarrier({
        barrier,
        x: -PAPER_WIDTH,
        y: 10,
        style: solidStyle('#111111'),
      }).ok,
    ).toBe(false)
  })
})
