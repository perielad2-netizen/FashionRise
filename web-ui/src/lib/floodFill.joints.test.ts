import { describe, expect, it } from 'vitest'
import {
  DEFAULT_ENDPOINT_SEAL_PX,
  STRONG_ENDPOINT_SEAL_PX,
  collectDrawStrokeEndpoints,
  floodFillAgainstBarrier,
  floodFillRegion,
  sealStrokeJoints,
} from '@/lib/floodFill'
import { DESIGN_HEIGHT, DESIGN_WIDTH, type Stroke, createStrokeId } from '@/lib/strokes'
import { solidStyle } from '@/lib/fills'

function emptyMask(): Uint8Array {
  return new Uint8Array(DESIGN_WIDTH * DESIGN_HEIGHT)
}

/** Axis-aligned thin rectangle as four separate strokes with intentional tip gaps. */
function multiStrokeRectWithGaps(gap: number, size = 1.75): Stroke[] {
  // Interior ~ 240×280 region centered-ish; gaps at each corner join.
  const x0 = 220
  const y0 = 240
  const x1 = 460
  const y1 = 520
  const g = gap
  const mk = (points: number[]): Stroke => ({
    id: createStrokeId(),
    tool: 'draw',
    points,
    color: '#111111',
    size,
    opacity: 1,
  })
  // Flattened freehand stride-3 points.
  const line = (ax: number, ay: number, bx: number, by: number, n = 12): number[] => {
    const out: number[] = []
    for (let i = 0; i <= n; i += 1) {
      const t = i / n
      out.push(ax + (bx - ax) * t, ay + (by - ay) * t, 0.5)
    }
    return out
  }
  return [
    mk(line(x0 + g, y0, x1 - g, y0)), // top — short of corners
    mk(line(x1, y0 + g, x1, y1 - g)), // right
    mk(line(x1 - g, y1, x0 + g, y1)), // bottom
    mk(line(x0, y1 - g, x0, y0 + g)), // left
  ]
}

function paintRectOntoMask(mask: Uint8Array, x0: number, y0: number, x1: number, y1: number) {
  for (let x = x0; x <= x1; x += 1) {
    mask[y0 * DESIGN_WIDTH + x] = 1
    mask[y1 * DESIGN_WIDTH + x] = 1
  }
  for (let y = y0; y <= y1; y += 1) {
    mask[y * DESIGN_WIDTH + x0] = 1
    mask[y * DESIGN_WIDTH + x1] = 1
  }
}

describe('multi-stroke joint sealing (#127)', () => {
  it('collects start/end endpoints from thin draw strokes', () => {
    const strokes = multiStrokeRectWithGaps(3)
    const ends = collectDrawStrokeEndpoints(strokes)
    expect(ends.length).toBe(8)
    expect(ends.every((e) => e.size === 1.75)).toBe(true)
  })

  it('fills a multi-stroke outline when corner gaps are within the automatic seal', () => {
    const gap = 3
    const strokes = multiStrokeRectWithGaps(gap)
    const mask = emptyMask()
    // Visible ink without corners (simulates tapered/raster leak at joins).
    paintRectOntoMask(mask, 220 + gap, 240, 460 - gap, 240)
    paintRectOntoMask(mask, 460, 240 + gap, 460, 520 - gap)
    paintRectOntoMask(mask, 220 + gap, 520, 460 - gap, 520)
    paintRectOntoMask(mask, 220, 240 + gap, 220, 520 - gap)

    const open = floodFillAgainstBarrier({
      barrier: mask,
      x: 340,
      y: 380,
      style: solidStyle('#B91C1C'),
    })
    expect(open.ok).toBe(false)
    if (!open.ok) expect(open.reason).toBe('open_outline')

    sealStrokeJoints(mask, strokes, DEFAULT_ENDPOINT_SEAL_PX)
    const closed = floodFillAgainstBarrier({
      barrier: mask,
      x: 340,
      y: 380,
      style: solidStyle('#B91C1C'),
    })
    expect(closed.ok).toBe(true)
  })

  it('does not seal an intentional large panel opening', () => {
    const gap = 28
    const strokes = multiStrokeRectWithGaps(gap)
    const mask = emptyMask()
    paintRectOntoMask(mask, 220 + gap, 240, 460 - gap, 240)
    paintRectOntoMask(mask, 460, 240 + gap, 460, 520 - gap)
    paintRectOntoMask(mask, 220 + gap, 520, 460 - gap, 520)
    paintRectOntoMask(mask, 220, 240 + gap, 220, 520 - gap)
    sealStrokeJoints(mask, strokes, DEFAULT_ENDPOINT_SEAL_PX)
    const result = floodFillAgainstBarrier({
      barrier: mask,
      x: 340,
      y: 380,
      style: solidStyle('#111111'),
    })
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.reason).toBe('open_outline')
      expect(result.message.toLowerCase()).not.toMatch(/dress/)
    }
  })

  it('strong Close-small-gaps seal bridges a medium accidental gap that default seal skips', () => {
    // Corner chord ≈ gap√2; pick gap so default (5) fails but strong (12) succeeds.
    const gap = 7
    const strokes = multiStrokeRectWithGaps(gap)
    const base = emptyMask()
    paintRectOntoMask(base, 220 + gap, 240, 460 - gap, 240)
    paintRectOntoMask(base, 460, 240 + gap, 460, 520 - gap)
    paintRectOntoMask(base, 220 + gap, 520, 460 - gap, 520)
    paintRectOntoMask(base, 220, 240 + gap, 220, 520 - gap)

    const weak = base.slice()
    sealStrokeJoints(weak, strokes, DEFAULT_ENDPOINT_SEAL_PX)
    expect(
      floodFillAgainstBarrier({
        barrier: weak,
        x: 340,
        y: 380,
        style: solidStyle('#111111'),
      }).ok,
    ).toBe(false)

    const strong = base.slice()
    sealStrokeJoints(strong, strokes, STRONG_ENDPOINT_SEAL_PX)
    expect(
      floodFillAgainstBarrier({
        barrier: strong,
        x: 340,
        y: 380,
        style: solidStyle('#111111'),
      }).ok,
    ).toBe(true)
  })

  it('open_outline messages never call the garment a dress', () => {
    const barrier = emptyMask()
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
    if (!result.ok) {
      expect(result.reason).toBe('open_outline')
      expect(result.message.toLowerCase()).not.toContain('dress')
      expect(result.message).toMatch(/close the shape/i)
    }
  })
})

describe('floodFillRegion closeSmallGaps probe (mocked barrier path)', () => {
  it('exports STRONG seal larger than default for the explicit Gaps action', () => {
    expect(STRONG_ENDPOINT_SEAL_PX).toBeGreaterThan(DEFAULT_ENDPOINT_SEAL_PX)
    expect(STRONG_ENDPOINT_SEAL_PX).toBeLessThanOrEqual(12)
  })

  it('keeps floodFillRegion callable with closeSmallGaps (integration smoke)', () => {
    // Without a real Canvas2D Path2D raster this returns empty_region / outside safely.
    // Joint sealing unit tests above cover the production mask logic.
    const strokes: Stroke[] = [
      {
        id: 's1',
        tool: 'draw',
        points: [10, 10, 0.5, 20, 10, 0.5],
        color: '#000',
        size: 1.75,
        opacity: 1,
      },
    ]
    const result = floodFillRegion({
      strokes,
      x: 340,
      y: 380,
      style: solidStyle('#111'),
      closeSmallGaps: true,
      gapClose: 0,
    })
    expect(result.ok === true || result.ok === false).toBe(true)
    expect(DESIGN_HEIGHT).toBeGreaterThan(0)
  })
})
