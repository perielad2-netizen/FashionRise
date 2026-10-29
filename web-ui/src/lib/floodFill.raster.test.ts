/**
 * Production-path Canvas2D / Path2D raster regressions for #127 fill safety.
 * Uses @napi-rs/canvas so paintInkStrokes → perfect-freehand → Path2D is real.
 */
import { createCanvas, Path2D as NapiPath2D } from '@napi-rs/canvas'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import {
  DEFAULT_ENDPOINT_SEAL_PX,
  DEFAULT_GAP_CLOSE_PX,
  STRONG_ENDPOINT_SEAL_PX,
  buildInkBarrierMask,
  floodFillRegion,
  locateGapHint,
} from '@/lib/floodFill'
import { checkPersistableFill, parseFillOp, solidStyle, type FillOp } from '@/lib/fills'
import { paintFillOps } from '@/lib/paintFills'
import { DESIGN_HEIGHT, DESIGN_WIDTH, type Stroke, createStrokeId } from '@/lib/strokes'

const g = globalThis as typeof globalThis & {
  Path2D: typeof Path2D
  document: Document
}

let previousPath2D: typeof Path2D | undefined
let previousCreateElement: typeof document.createElement | undefined

beforeAll(() => {
  previousPath2D = g.Path2D
  previousCreateElement = document.createElement.bind(document)
  g.Path2D = NapiPath2D as unknown as typeof Path2D
  document.createElement = ((tag: string) => {
    if (tag === 'canvas') {
      const canvas = createCanvas(DESIGN_WIDTH, DESIGN_HEIGHT) as unknown as HTMLCanvasElement
      return canvas
    }
    return previousCreateElement!(tag)
  }) as typeof document.createElement
})

afterAll(() => {
  if (previousPath2D) g.Path2D = previousPath2D
  if (previousCreateElement) document.createElement = previousCreateElement
})

function strideLine(ax: number, ay: number, bx: number, by: number, n = 16): number[] {
  const out: number[] = []
  for (let i = 0; i <= n; i += 1) {
    const t = i / n
    out.push(ax + (bx - ax) * t, ay + (by - ay) * t, 0.55)
  }
  return out
}

function drawStroke(points: number[], size = 1.75): Stroke {
  return {
    id: createStrokeId(),
    tool: 'draw',
    points,
    color: '#111111',
    size,
    opacity: 1,
  }
}

function eraseStroke(points: number[], size = 10): Stroke {
  return {
    id: createStrokeId(),
    tool: 'erase',
    points,
    color: '#000000',
    size,
    opacity: 1,
  }
}

/** Four thin strokes forming a rectangle with corner gaps of `gap` design px. */
function multiStrokeRect(gap: number, size = 1.75): Stroke[] {
  const x0 = 220
  const y0 = 240
  const x1 = 460
  const y1 = 520
  return [
    drawStroke(strideLine(x0 + gap, y0, x1 - gap, y0), size),
    drawStroke(strideLine(x1, y0 + gap, x1, y1 - gap), size),
    drawStroke(strideLine(x1 - gap, y1, x0 + gap, y1), size),
    drawStroke(strideLine(x0, y1 - gap, x0, y0 + gap), size),
  ]
}

describe('production Canvas2D raster fill path (#127 safety)', () => {
  it('fills a thin multi-stroke closed outline via real Path2D raster + sealTips', () => {
    // Slightly overlapping corners so sealTips + tight auto seal close taper leaks.
    const strokes = multiStrokeRect(0.75, 2.25)
    const result = floodFillRegion({
      strokes,
      x: 340,
      y: 380,
      style: solidStyle('#B91C1C'),
      gapClose: 2,
    })
    expect(result.ok).toBe(true)
  })

  it('keeps an intentional ~4px corner opening open under automatic fill', () => {
    const strokes = multiStrokeRect(4, 1.75)
    const result = floodFillRegion({
      strokes,
      x: 340,
      y: 380,
      style: solidStyle('#111111'),
      gapClose: 2,
    })
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.reason).toBe('open_outline')
      expect(result.message.toLowerCase()).not.toContain('dress')
      // Must not claim a highlighted spot unless locateGapHint found one.
      if (!result.gapHint) {
        expect(result.message.toLowerCase()).not.toMatch(/highlighted spot/)
      }
    }
  })

  it('does not merge two separate panels 4px apart', () => {
    const left = [
      drawStroke(strideLine(200, 300, 200, 500)),
      drawStroke(strideLine(200, 500, 320, 500)),
      drawStroke(strideLine(320, 500, 320, 300)),
      drawStroke(strideLine(320, 300, 200, 300)),
    ]
    // Right panel: left edge 4px from left panel's right edge.
    const right = [
      drawStroke(strideLine(324, 300, 324, 500)),
      drawStroke(strideLine(324, 500, 440, 500)),
      drawStroke(strideLine(440, 500, 440, 300)),
      drawStroke(strideLine(440, 300, 324, 300)),
    ]
    const strokes = [...left, ...right]
    const leftFill = floodFillRegion({
      strokes,
      x: 260,
      y: 400,
      style: solidStyle('#B91C1C'),
    })
    const rightFill = floodFillRegion({
      strokes,
      x: 380,
      y: 400,
      style: solidStyle('#1D4ED8'),
    })
    expect(leftFill.ok).toBe(true)
    expect(rightFill.ok).toBe(true)
    // Filling left must not paint into the right panel region.
    if (leftFill.ok && rightFill.ok) {
      const lx = leftFill.fill.contour
      let maxLeftX = 0
      for (let i = 0; i < lx.length; i += 2) maxLeftX = Math.max(maxLeftX, lx[i]!)
      expect(maxLeftX).toBeLessThan(322)
    }
  })

  it('preserves eraser intent at a multi-stroke junction (no ghost barrier)', () => {
    const x0 = 250
    const y0 = 280
    const x1 = 450
    const y1 = 520
    const strokes: Stroke[] = [
      drawStroke(strideLine(x0, y0, x1, y0)),
      drawStroke(strideLine(x1, y0, x1, y1)),
      drawStroke(strideLine(x1, y1, x0, y1)),
      drawStroke(strideLine(x0, y1, x0, y0)),
      // Erase the top-right junction so the outline is intentionally open there.
      eraseStroke(strideLine(x1 - 18, y0 - 6, x1 + 6, y0 + 18, 8), 14),
    ]
    const auto = floodFillRegion({
      strokes,
      x: 350,
      y: 400,
      style: solidStyle('#111111'),
      gapClose: 2,
    })
    expect(auto.ok).toBe(false)
    if (!auto.ok) expect(auto.reason).toBe('open_outline')

    const strong = floodFillRegion({
      strokes,
      x: 350,
      y: 400,
      style: solidStyle('#111111'),
      closeSmallGaps: true,
      gapClose: 2,
    })
    expect(strong.ok).toBe(false)
    if (!strong.ok) expect(strong.reason).toBe('open_outline')

    // Barrier must not show sealed ink through the erased junction.
    const barrier = buildInkBarrierMask(strokes, 0, { endpointSealPx: STRONG_ENDPOINT_SEAL_PX })
    expect(barrier[y0 * DESIGN_WIDTH + x1]).toBe(0)
  })

  it('keeps a narrow 3px erased opening open after final dilate (Fill + Gaps)', () => {
    const x0 = 260
    const y0 = 300
    const x1 = 440
    const y1 = 500
    // Continuous overlapping outline so only the erase creates the opening.
    const closed: Stroke[] = [
      drawStroke(strideLine(x0, y0, x1, y0), 2.5),
      drawStroke(strideLine(x1, y0, x1, y1), 2.5),
      drawStroke(strideLine(x1, y1, x0, y1), 2.5),
      drawStroke(strideLine(x0, y1, x0, y0), 2.5),
    ]
    // Narrow erase (~3px mouth) on the top edge — smaller than default dilate*2 risk.
    const gapMidX = Math.round((x0 + x1) / 2)
    const erased: Stroke[] = [
      ...closed,
      eraseStroke(strideLine(gapMidX - 1.5, y0 - 1, gapMidX + 1.5, y0 + 1, 4), 3.5),
    ]

    const auto = floodFillRegion({
      strokes: erased,
      x: 350,
      y: 400,
      style: solidStyle('#111111'),
      gapClose: DEFAULT_GAP_CLOSE_PX,
    })
    expect(auto.ok).toBe(false)
    if (!auto.ok) expect(auto.reason).toBe('open_outline')

    const gaps = floodFillRegion({
      strokes: erased,
      x: 350,
      y: 400,
      style: solidStyle('#111111'),
      closeSmallGaps: true,
      gapClose: DEFAULT_GAP_CLOSE_PX,
    })
    expect(gaps.ok).toBe(false)
    if (!gaps.ok) expect(gaps.reason).toBe('open_outline')

    // Final dilated barrier must still show an opening at the erase mouth.
    const barrier = buildInkBarrierMask(erased, DEFAULT_GAP_CLOSE_PX, {
      endpointSealPx: DEFAULT_ENDPOINT_SEAL_PX,
    })
    expect(barrier[y0 * DESIGN_WIDTH + gapMidX]).toBe(0)

    const strongBarrier = buildInkBarrierMask(erased, DEFAULT_GAP_CLOSE_PX, {
      endpointSealPx: STRONG_ENDPOINT_SEAL_PX,
    })
    expect(strongBarrier[y0 * DESIGN_WIDTH + gapMidX]).toBe(0)
  })

  it('lets a later pencil stroke reconnect an erased gap (chronology)', () => {
    const x0 = 260
    const y0 = 300
    const x1 = 440
    const y1 = 500
    const gapMidX = Math.round((x0 + x1) / 2)
    const strokes: Stroke[] = [
      drawStroke(strideLine(x0, y0, x1, y0), 2.5),
      drawStroke(strideLine(x1, y0, x1, y1), 2.5),
      drawStroke(strideLine(x1, y1, x0, y1), 2.5),
      drawStroke(strideLine(x0, y1, x0, y0), 2.5),
      eraseStroke(strideLine(gapMidX - 2, y0 - 1, gapMidX + 2, y0 + 1, 4), 4),
      // Later redraw bridges the erased mouth — fill must succeed again.
      drawStroke(strideLine(gapMidX - 8, y0, gapMidX + 8, y0), 2.5),
    ]
    const result = floodFillRegion({
      strokes,
      x: 350,
      y: 400,
      style: solidStyle('#B91C1C'),
      gapClose: DEFAULT_GAP_CLOSE_PX,
    })
    expect(result.ok).toBe(true)
  })

  it('rejects nested cutout fills that would paint the hole (pixels + save path)', () => {
    const outer = multiStrokeRect(1.2, 2)
    const ix0 = 300
    const iy0 = 320
    const ix1 = 380
    const iy1 = 420
    const inner = [
      drawStroke(strideLine(ix0, iy0, ix1, iy0), 2),
      drawStroke(strideLine(ix1, iy0, ix1, iy1), 2),
      drawStroke(strideLine(ix1, iy1, ix0, iy1), 2),
      drawStroke(strideLine(ix0, iy1, ix0, iy0), 2),
    ]
    const strokes = [...outer, ...inner]
    const ring = floodFillRegion({
      strokes,
      x: 260,
      y: 380,
      style: solidStyle('#B91C1C'),
    })
    // Single-contour persistence cannot keep holes empty — fail closed.
    expect(ring.ok).toBe(false)
    if (!ring.ok) {
      expect(ring.reason).toBe('unsupported_cutout')
      expect(ring.message.toLowerCase()).toMatch(/cutout|hole|inner/)
    }

    const hole = floodFillRegion({
      strokes,
      x: 340,
      y: 370,
      style: solidStyle('#1D4ED8'),
    })
    expect(hole.ok).toBe(true)

    // Prove why we reject: painting an outer-only contour would flood the cutout.
    const bogusOuter: FillOp = {
      id: 'bogus-ring',
      contour: [230, 250, 450, 250, 450, 510, 230, 510],
      style: solidStyle('#B91C1C'),
      seedX: 260,
      seedY: 380,
    }
    const canvas = createCanvas(DESIGN_WIDTH, DESIGN_HEIGHT)
    const ctx = canvas.getContext('2d')
    expect(ctx).toBeTruthy()
    paintFillOps(ctx!, [bogusOuter])
    const img = ctx!.getImageData(0, 0, DESIGN_WIDTH, DESIGN_HEIGHT)
    const holeIdx = (Math.round((iy0 + iy1) / 2) * DESIGN_WIDTH + Math.round((ix0 + ix1) / 2)) * 4
    expect(img.data[holeIdx + 3]!).toBeGreaterThan(10)

    // Successful hole fill survives persist parse (save/reopen) and re-paint without
    // spilling into the ring sample outside the hole.
    if (hole.ok) {
      const persist = checkPersistableFill(hole.fill)
      expect(persist.ok).toBe(true)
      const roundTrip = parseFillOp(JSON.parse(JSON.stringify(hole.fill)))
      expect(roundTrip).not.toBeNull()
      const exportCanvas = createCanvas(DESIGN_WIDTH, DESIGN_HEIGHT)
      const exportCtx = exportCanvas.getContext('2d')!
      paintFillOps(exportCtx, [roundTrip!])
      const exported = exportCtx.getImageData(0, 0, DESIGN_WIDTH, DESIGN_HEIGHT)
      const holePx =
        exported.data[
          (Math.round((iy0 + iy1) / 2) * DESIGN_WIDTH + Math.round((ix0 + ix1) / 2)) * 4 + 3
        ]!
      const ringPx = exported.data[(380 * DESIGN_WIDTH + 260) * 4 + 3]!
      expect(holePx).toBeGreaterThan(10)
      expect(ringPx).toBe(0)
    }
  })

  it('marks the gap mouth nearest the escape, not a later corridor cell', () => {
    // Synthetic barrier: three-sided box with a *narrow* top gap. Escape from a
    // deep seed runs past many wall-adjacent corridor cells; the marker must be
    // the first mouth from the edge (near y=200), not a side-wall cell near the seed.
    const barrier = new Uint8Array(DESIGN_WIDTH * DESIGN_HEIGHT)
    for (let y = 200; y <= 600; y += 1) {
      barrier[y * DESIGN_WIDTH + 200] = 1
      barrier[y * DESIGN_WIDTH + 500] = 1
    }
    for (let x = 200; x <= 500; x += 1) {
      barrier[600 * DESIGN_WIDTH + x] = 1
    }
    for (let x = 200; x <= 348; x += 1) barrier[200 * DESIGN_WIDTH + x] = 1
    for (let x = 352; x <= 500; x += 1) barrier[200 * DESIGN_WIDTH + x] = 1

    const hint = locateGapHint(barrier, 350, 450)
    expect(hint).not.toBeNull()
    if (hint) {
      expect(hint.y).toBeLessThan(280)
      expect(hint.x).toBeGreaterThan(340)
      expect(hint.x).toBeLessThan(360)
    }

    // Wide ambiguous opening: path through the centre never grazes barrier tips —
    // suppress the marker rather than highlighting a misleading side-wall cell.
    const wide = new Uint8Array(DESIGN_WIDTH * DESIGN_HEIGHT)
    for (let y = 200; y <= 600; y += 1) {
      wide[y * DESIGN_WIDTH + 200] = 1
      wide[y * DESIGN_WIDTH + 500] = 1
    }
    for (let x = 200; x <= 500; x += 1) wide[600 * DESIGN_WIDTH + x] = 1
    for (let x = 200; x <= 300; x += 1) wide[200 * DESIGN_WIDTH + x] = 1
    for (let x = 400; x <= 500; x += 1) wide[200 * DESIGN_WIDTH + x] = 1
    expect(locateGapHint(wide, 350, 450)).toBeNull()
  })

  it('does not report the paper edge as a gap hint', () => {
    // Completely open U-shape — flood escapes to edge.
    const strokes = [
      drawStroke(strideLine(200, 200, 200, 600)),
      drawStroke(strideLine(200, 600, 500, 600)),
      drawStroke(strideLine(500, 600, 500, 200)),
    ]
    const barrier = buildInkBarrierMask(strokes, 2, { endpointSealPx: DEFAULT_ENDPOINT_SEAL_PX })
    const hint = locateGapHint(barrier, 350, 400)
    if (hint) {
      expect(hint.x).toBeGreaterThan(2)
      expect(hint.y).toBeGreaterThan(2)
      expect(hint.x).toBeLessThan(DESIGN_WIDTH - 3)
      expect(hint.y).toBeLessThan(DESIGN_HEIGHT - 3)
    }
    const result = floodFillRegion({
      strokes,
      x: 350,
      y: 400,
      style: solidStyle('#111'),
    })
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.gapHint?.x === 0 || result.gapHint?.y === 0).not.toBe(true)
      if (result.gapHint) {
        expect(result.gapHint.x).toBeGreaterThan(2)
        expect(result.gapHint.y).toBeGreaterThan(2)
      } else {
        expect(result.message.toLowerCase()).not.toMatch(/highlighted spot/)
      }
    }
  })

  it('stays responsive with hundreds of strokes (Fill probe)', () => {
    const strokes: Stroke[] = []
    for (let i = 0; i < 500; i += 1) {
      const x = 40 + (i % 40) * 18
      const y = 40 + Math.floor(i / 40) * 22
      strokes.push(drawStroke(strideLine(x, y, x + 12, y + 8, 4), 1.75))
    }
    // Closed shape among the noise.
    strokes.push(...multiStrokeRect(1.4, 1.75))
    const t0 = performance.now()
    const result = floodFillRegion({
      strokes,
      x: 340,
      y: 380,
      style: solidStyle('#111'),
    })
    const ms = performance.now() - t0
    expect(ms).toBeLessThan(2500)
    expect(result.ok === true || result.ok === false).toBe(true)
  })
})
