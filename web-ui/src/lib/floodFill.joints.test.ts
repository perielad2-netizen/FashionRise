import { describe, expect, it } from 'vitest'
import {
  DEFAULT_ENDPOINT_SEAL_PX,
  STRONG_ENDPOINT_SEAL_PX,
  collectDrawStrokeEndpoints,
  floodFillAgainstBarrier,
  sealStrokeJoints,
} from '@/lib/floodFill'
import { DESIGN_HEIGHT, DESIGN_WIDTH, type Stroke, createStrokeId } from '@/lib/strokes'
import { solidStyle } from '@/lib/fills'

function emptyMask(): Uint8Array {
  return new Uint8Array(DESIGN_WIDTH * DESIGN_HEIGHT)
}

/** Axis-aligned thin rectangle as four separate strokes with intentional tip gaps. */
function multiStrokeRectWithGaps(gap: number, size = 1.75): Stroke[] {
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
  const line = (ax: number, ay: number, bx: number, by: number, n = 12): number[] => {
    const out: number[] = []
    for (let i = 0; i <= n; i += 1) {
      const t = i / n
      out.push(ax + (bx - ax) * t, ay + (by - ay) * t, 0.5)
    }
    return out
  }
  return [
    mk(line(x0 + g, y0, x1 - g, y0)),
    mk(line(x1, y0 + g, x1, y1 - g)),
    mk(line(x1 - g, y1, x0 + g, y1)),
    mk(line(x0, y1 - g, x0, y0 + g)),
  ]
}

function paintRectOntoMask(mask: Uint8Array, x0: number, y0: number, x1: number, y1: number) {
  const ax0 = Math.round(Math.min(x0, x1))
  const ax1 = Math.round(Math.max(x0, x1))
  const ay0 = Math.round(Math.min(y0, y1))
  const ay1 = Math.round(Math.max(y0, y1))
  for (let x = ax0; x <= ax1; x += 1) {
    mask[ay0 * DESIGN_WIDTH + x] = 1
    mask[ay1 * DESIGN_WIDTH + x] = 1
  }
  for (let y = ay0; y <= ay1; y += 1) {
    mask[y * DESIGN_WIDTH + ax0] = 1
    mask[y * DESIGN_WIDTH + ax1] = 1
  }
}

function paintAliveTips(mask: Uint8Array, strokes: Stroke[]) {
  // Stamp only the tip pixel so helper ink cannot accidentally bridge openings.
  for (const e of collectDrawStrokeEndpoints(strokes)) {
    const x = Math.round(e.x)
    const y = Math.round(e.y)
    if (x >= 0 && y >= 0 && x < DESIGN_WIDTH && y < DESIGN_HEIGHT) {
      mask[y * DESIGN_WIDTH + x] = 1
    }
  }
}

describe('multi-stroke joint sealing (#127)', () => {
  it('collects start/end endpoints with tip tangents from thin draw strokes', () => {
    const strokes = multiStrokeRectWithGaps(3)
    const ends = collectDrawStrokeEndpoints(strokes)
    expect(ends.length).toBe(8)
    expect(ends.every((e) => e.size === 1.75)).toBe(true)
    expect(ends.every((e) => Number.isFinite(e.tx) && Number.isFinite(e.ty))).toBe(true)
  })

  it('fills a multi-stroke outline when corner gaps are within the automatic seal', () => {
    // gap√2 must be ≤ DEFAULT_ENDPOINT_SEAL_PX (2.5)
    const gap = 1.5
    const strokes = multiStrokeRectWithGaps(gap)
    const mask = emptyMask()
    paintRectOntoMask(mask, 220 + gap, 240, 460 - gap, 240)
    paintRectOntoMask(mask, 460, 240 + gap, 460, 520 - gap)
    paintRectOntoMask(mask, 220 + gap, 520, 460 - gap, 520)
    paintRectOntoMask(mask, 220, 240 + gap, 220, 520 - gap)
    paintAliveTips(mask, strokes)

    const open = floodFillAgainstBarrier({
      barrier: mask.slice(),
      x: 340,
      y: 380,
      style: solidStyle('#B91C1C'),
    })
    expect(open.ok).toBe(false)

    const sealed = mask.slice()
    sealStrokeJoints(sealed, strokes, DEFAULT_ENDPOINT_SEAL_PX)
    const closed = floodFillAgainstBarrier({
      barrier: sealed,
      x: 340,
      y: 380,
      style: solidStyle('#B91C1C'),
    })
    expect(closed.ok).toBe(true)
  })

  it('does not automatically seal an intentional 4px corner opening', () => {
    const gap = 4
    const strokes = multiStrokeRectWithGaps(gap)
    const mask = emptyMask()
    paintRectOntoMask(mask, 220 + gap, 240, 460 - gap, 240)
    paintRectOntoMask(mask, 460, 240 + gap, 460, 520 - gap)
    paintRectOntoMask(mask, 220 + gap, 520, 460 - gap, 520)
    paintRectOntoMask(mask, 220, 240 + gap, 220, 520 - gap)
    paintAliveTips(mask, strokes)
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

  it('does not seal an intentional large panel opening', () => {
    const gap = 28
    const strokes = multiStrokeRectWithGaps(gap)
    const mask = emptyMask()
    paintRectOntoMask(mask, 220 + gap, 240, 460 - gap, 240)
    paintRectOntoMask(mask, 460, 240 + gap, 460, 520 - gap)
    paintRectOntoMask(mask, 220 + gap, 520, 460 - gap, 520)
    paintRectOntoMask(mask, 220, 240 + gap, 220, 520 - gap)
    paintAliveTips(mask, strokes)
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

  it('does not bridge side-by-side panel edges within the seal radius (no facing)', () => {
    // Two vertical edges 4px apart — parallel tangents, should not join.
    const left: Stroke = {
      id: 'L',
      tool: 'draw',
      points: [300, 300, 0.5, 300, 400, 0.5, 300, 500, 0.5],
      color: '#111',
      size: 2,
      opacity: 1,
    }
    const right: Stroke = {
      id: 'R',
      tool: 'draw',
      points: [304, 300, 0.5, 304, 400, 0.5, 304, 500, 0.5],
      color: '#111',
      size: 2,
      opacity: 1,
    }
    const mask = emptyMask()
    for (let y = 300; y <= 500; y += 1) {
      mask[y * DESIGN_WIDTH + 300] = 1
      mask[y * DESIGN_WIDTH + 304] = 1
    }
    sealStrokeJoints(mask, [left, right], STRONG_ENDPOINT_SEAL_PX)
    // Mid-gap between panels must stay empty.
    expect(mask[400 * DESIGN_WIDTH + 302]).toBe(0)
  })

  it('strong Close-small-gaps seal bridges a medium accidental gap that default seal skips', () => {
    const gap = 7
    const strokes = multiStrokeRectWithGaps(gap)
    const base = emptyMask()
    paintRectOntoMask(base, 220 + gap, 240, 460 - gap, 240)
    paintRectOntoMask(base, 460, 240 + gap, 460, 520 - gap)
    paintRectOntoMask(base, 220 + gap, 520, 460 - gap, 520)
    paintRectOntoMask(base, 220, 240 + gap, 220, 520 - gap)
    paintAliveTips(base, strokes)

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

  it('erase coverage vetoes resealing a deliberately cleared junction', () => {
    const gap = 2
    const strokes = multiStrokeRectWithGaps(gap)
    const mask = emptyMask()
    paintRectOntoMask(mask, 220 + gap, 240, 460 - gap, 240)
    paintRectOntoMask(mask, 460, 240 + gap, 460, 520 - gap)
    paintRectOntoMask(mask, 220 + gap, 520, 460 - gap, 520)
    paintRectOntoMask(mask, 220, 240 + gap, 220, 520 - gap)
    paintAliveTips(mask, strokes)

    // Simulate erase covering the top-right corner join corridor.
    const eraseCoverage = emptyMask()
    for (let y = 238; y <= 248; y += 1) {
      for (let x = 454; x <= 464; x += 1) {
        eraseCoverage[y * DESIGN_WIDTH + x] = 1
        mask[y * DESIGN_WIDTH + x] = 0
      }
    }
    sealStrokeJoints(mask, strokes, STRONG_ENDPOINT_SEAL_PX, { eraseCoverage })
    // Ghost barrier must not reappear in the erased corridor.
    expect(mask[243 * DESIGN_WIDTH + 458]).toBe(0)
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
      expect(result.gapHint).toBeUndefined()
    }
  })

  it('exports automatic seal tighter than Gaps and below intentional 4px openings', () => {
    expect(STRONG_ENDPOINT_SEAL_PX).toBeGreaterThan(DEFAULT_ENDPOINT_SEAL_PX)
    expect(DEFAULT_ENDPOINT_SEAL_PX).toBeLessThan(4)
    expect(STRONG_ENDPOINT_SEAL_PX).toBeLessThanOrEqual(12)
    expect(DESIGN_HEIGHT).toBeGreaterThan(0)
  })
})
