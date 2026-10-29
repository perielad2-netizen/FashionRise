import { describe, expect, it } from 'vitest'
import { floodFillAgainstBarrier } from '@/lib/floodFill'
import { DESIGN_HEIGHT, DESIGN_WIDTH } from '@/lib/strokes'
import { solidStyle } from '@/lib/fills'

function emptyBarrier(): Uint8Array {
  return new Uint8Array(DESIGN_WIDTH * DESIGN_HEIGHT)
}

/** Closed rectangle ring so the interior is fillable and does not touch the paper edge. */
function closedRectBarrier(x0: number, y0: number, x1: number, y1: number): Uint8Array {
  const barrier = emptyBarrier()
  for (let x = x0; x <= x1; x += 1) {
    barrier[y0 * DESIGN_WIDTH + x] = 1
    barrier[y1 * DESIGN_WIDTH + x] = 1
  }
  for (let y = y0; y <= y1; y += 1) {
    barrier[y * DESIGN_WIDTH + x0] = 1
    barrier[y * DESIGN_WIDTH + x1] = 1
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
    // Contour stays inside the barrier box.
    for (let i = 0; i < result.fill.contour.length; i += 2) {
      expect(result.fill.contour[i]!).toBeGreaterThanOrEqual(200)
      expect(result.fill.contour[i]!).toBeLessThanOrEqual(400)
      expect(result.fill.contour[i + 1]!).toBeGreaterThanOrEqual(200)
      expect(result.fill.contour[i + 1]!).toBeLessThanOrEqual(420)
    }
  })

  it('fills bodice and skirt regions independently', () => {
    const barrier = emptyBarrier()
    // Outer dress silhouette
    for (let x = 250; x <= 450; x += 1) {
      barrier[180 * DESIGN_WIDTH + x] = 1
      barrier[700 * DESIGN_WIDTH + x] = 1
    }
    for (let y = 180; y <= 700; y += 1) {
      barrier[y * DESIGN_WIDTH + 250] = 1
      barrier[y * DESIGN_WIDTH + 450] = 1
    }
    // Waist seam separating bodice / skirt
    for (let x = 250; x <= 450; x += 1) {
      barrier[380 * DESIGN_WIDTH + x] = 1
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
    expect(bodiceMaxY).toBeLessThanOrEqual(380)
    expect(skirtMinY).toBeGreaterThanOrEqual(380)
  })

  it('rejects open outlines that leak to the paper edge', () => {
    const barrier = emptyBarrier()
    // Three sides only — open at the top.
    for (let y = 200; y <= 500; y += 1) {
      barrier[y * DESIGN_WIDTH + 200] = 1
      barrier[y * DESIGN_WIDTH + 400] = 1
    }
    for (let x = 200; x <= 400; x += 1) {
      barrier[500 * DESIGN_WIDTH + x] = 1
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

  it('rejects taps on the barrier and outside the design space', () => {
    const barrier = closedRectBarrier(100, 100, 200, 200)
    expect(
      floodFillAgainstBarrier({
        barrier,
        x: 100,
        y: 150,
        style: solidStyle('#111111'),
      }).ok,
    ).toBe(false)
    expect(
      floodFillAgainstBarrier({
        barrier,
        x: -1,
        y: 10,
        style: solidStyle('#111111'),
      }).ok,
    ).toBe(false)
  })
})
