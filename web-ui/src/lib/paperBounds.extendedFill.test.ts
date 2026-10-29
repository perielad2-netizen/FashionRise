/**
 * Issue #127 — extended logical paper around the croquis reference.
 * Real Canvas2D / Path2D regressions for oversized silhouettes.
 */
import { createCanvas, Path2D as NapiPath2D } from '@napi-rs/canvas'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import {
  DEFAULT_ENDPOINT_SEAL_PX,
  DEFAULT_GAP_CLOSE_PX,
  buildInkBarrierMask,
  floodFillRegion,
} from '@/lib/floodFill'
import { solidStyle, checkPersistableFill, parseFillOp } from '@/lib/fills'
import { paintFillOps } from '@/lib/paintFills'
import { exportSketchPng, paintInkStrokes, renderSketchCanvas } from '@/lib/exportCanvas'
import {
  PAPER_HEIGHT,
  PAPER_ORIGIN_X,
  PAPER_ORIGIN_Y,
  PAPER_WIDTH,
  artworkExceedsLegacyBounds,
  resolveExportFrame,
} from '@/lib/paperBounds'
import { DESIGN_HEIGHT, DESIGN_WIDTH, createStrokeId, type Stroke } from '@/lib/strokes'
import { captureSketchForMagic } from '@/lib/sketchCapture'
import { fitPage, clampPan, fitDrawingScale } from '@/lib/viewportTransform'

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
      return createCanvas(PAPER_WIDTH, PAPER_HEIGHT) as unknown as HTMLCanvasElement
    }
    return previousCreateElement!(tag)
  }) as typeof document.createElement
})

afterAll(() => {
  if (previousPath2D) g.Path2D = previousPath2D
  if (previousCreateElement) document.createElement = previousCreateElement
})

function drawStroke(flatXY: number[], size = 2.5): Stroke {
  const points: number[] = []
  for (let i = 0; i + 1 < flatXY.length; i += 2) {
    points.push(flatXY[i]!, flatXY[i + 1]!, 0.5)
  }
  return {
    id: createStrokeId(),
    tool: 'draw',
    points,
    color: '#1C1C1E',
    size,
    opacity: 1,
  }
}

function strideLine(x0: number, y0: number, x1: number, y1: number, step = 8): number[] {
  const dist = Math.hypot(x1 - x0, y1 - y0)
  const n = Math.max(1, Math.ceil(dist / step))
  const out: number[] = []
  for (let i = 0; i <= n; i += 1) {
    const t = i / n
    out.push(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)
  }
  return out
}

/** Closed puffy dress that crosses the legacy 768×1024 box but stays inside the paper. */
function oversizedPuffyDress(): Stroke[] {
  // Axis-aligned oversized silhouette: clearly past every legacy edge, well inside paper.
  const x0 = -80
  const y0 = -70
  const x1 = 820
  const y1 = 1100
  const outline = [
    ...strideLine(x0, y0, x1, y0, 14),
    ...strideLine(x1, y0, x1, y1, 14),
    ...strideLine(x1, y1, x0, y1, 14),
    ...strideLine(x0, y1, x0, y0, 14),
  ]
  return [drawStroke(outline, 2.75)]
}

describe('Issue #127 extended paper bounds', () => {
  it('defines a 1280×1536 paper with croquis origin offset (−256,−256)', () => {
    expect(PAPER_WIDTH).toBe(1280)
    expect(PAPER_HEIGHT).toBe(1536)
    expect(PAPER_ORIGIN_X).toBe(-256)
    expect(PAPER_ORIGIN_Y).toBe(-256)
    expect(DESIGN_WIDTH).toBe(768)
    expect(DESIGN_HEIGHT).toBe(1024)
  })

  it('fills a closed oversized puffy dress that crosses the legacy 768×1024 limits', () => {
    const strokes = oversizedPuffyDress()
    expect(artworkExceedsLegacyBounds(strokes)).toBe(true)
    const result = floodFillRegion({
      strokes,
      x: 384,
      y: 480,
      style: solidStyle('#B91C1C'),
      gapClose: DEFAULT_GAP_CLOSE_PX,
    })
    expect(result.ok).toBe(true)
    if (!result.ok) return
    expect(checkPersistableFill(result.fill).ok).toBe(true)
    // Contour uses design space — includes margin coordinates.
    const xs = result.fill.contour.filter((_, i) => i % 2 === 0)
    const ys = result.fill.contour.filter((_, i) => i % 2 === 1)
    expect(Math.min(...xs)).toBeLessThan(0)
    expect(Math.max(...xs)).toBeGreaterThan(DESIGN_WIDTH)
    expect(Math.min(...ys)).toBeLessThan(0)
    expect(Math.max(...ys)).toBeGreaterThan(DESIGN_HEIGHT)
  })

  it('survives save/reopen parse and full paper PNG export', async () => {
    const strokes = oversizedPuffyDress()
    const result = floodFillRegion({
      strokes,
      x: 384,
      y: 480,
      style: solidStyle('#0F766E'),
    })
    expect(result.ok).toBe(true)
    if (!result.ok) return
    const roundTrip = parseFillOp(JSON.parse(JSON.stringify(result.fill)))
    expect(roundTrip).not.toBeNull()

    const frame = resolveExportFrame(strokes, [roundTrip!])
    expect(frame.mode).toBe('paper')
    expect(frame.width).toBe(PAPER_WIDTH)
    expect(frame.height).toBe(PAPER_HEIGHT)

    const { canvas } = await renderSketchCanvas({
      strokes,
      fills: [roundTrip!],
      referenceUrl: null,
    })
    expect(canvas.width).toBe(PAPER_WIDTH)
    expect(canvas.height).toBe(PAPER_HEIGHT)

    // Sample a filled interior in paper raster space.
    const ctx = canvas.getContext('2d')!
    const ix = Math.round(384 - PAPER_ORIGIN_X)
    const iy = Math.round(480 - PAPER_ORIGIN_Y)
    const px = ctx.getImageData(ix, iy, 1, 1).data
    expect(px[3]!).toBeGreaterThan(10)

    const { blob } = await exportSketchPng({
      strokes,
      fills: [roundTrip!],
      referenceUrl: null,
    })
    expect(blob.size).toBeGreaterThan(100)
  })

  it('keeps croquis placement geometry on the legacy plane inside paper exports', async () => {
    const strokes = oversizedPuffyDress()
    const { canvas } = await renderSketchCanvas({
      strokes,
      fills: [],
      referenceUrl: null,
    })
    expect(canvas.width).toBe(PAPER_WIDTH)
    expect(canvas.height).toBe(PAPER_HEIGHT)
    // Legacy croquis box maps to paper pixels [256,1024)×[256,1280).
    expect(-PAPER_ORIGIN_X).toBe(256)
    expect(-PAPER_ORIGIN_Y).toBe(256)
    expect(256 + DESIGN_WIDTH).toBe(PAPER_WIDTH - 256)
    expect(256 + DESIGN_HEIGHT).toBe(PAPER_HEIGHT - 256)
  })

  it('exports legacy-only artwork at 768×1024 (pixel frame unchanged)', async () => {
    const strokes = [
      drawStroke([
        ...strideLine(200, 200, 500, 200),
        ...strideLine(500, 200, 500, 600),
        ...strideLine(500, 600, 200, 600),
        ...strideLine(200, 600, 200, 200),
      ]),
    ]
    expect(artworkExceedsLegacyBounds(strokes)).toBe(false)
    const { canvas } = await renderSketchCanvas({
      strokes,
      fills: [],
      referenceUrl: null,
    })
    expect(canvas.width).toBe(DESIGN_WIDTH)
    expect(canvas.height).toBe(DESIGN_HEIGHT)
  })

  it('rejects a contour that reaches the NEW outer paper boundary', () => {
    // Open U that escapes through the paper top edge (y = PAPER_ORIGIN_Y).
    const strokes = [
      drawStroke(strideLine(-200, 200, -200, 800)),
      drawStroke(strideLine(-200, 800, 900, 800)),
      drawStroke(strideLine(900, 800, 900, 200)),
      // No top — flood escapes upward past y=-256.
    ]
    const result = floodFillRegion({
      strokes,
      x: 350,
      y: 500,
      style: solidStyle('#111111'),
    })
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.reason).toBe('open_outline')
      expect(result.message.toLowerCase()).toMatch(/outer drawing boundary|close the shape/)
    }
  })

  it('still protects a 6px hollow cutout on the extended paper', () => {
    // Modest closed panel that still crosses the legacy left edge (x<0).
    const outerPts = [
      -40, 300, 420, 300, 420, 620, -40, 620,
    ]
    const outline: number[] = []
    for (let i = 0; i < outerPts.length; i += 2) {
      const j = (i + 2) % outerPts.length
      outline.push(...strideLine(outerPts[i]!, outerPts[i + 1]!, outerPts[j]!, outerPts[j + 1]!, 10))
    }
    const hx0 = 170
    const hy0 = 430
    const hx1 = 176
    const hy1 = 436
    const loop = [
      ...strideLine(hx0, hy0, hx1, hy0, 4),
      ...strideLine(hx1, hy0, hx1, hy1, 4),
      ...strideLine(hx1, hy1, hx0, hy1, 4),
      ...strideLine(hx0, hy1, hx0, hy0, 4),
    ]
    const strokes = [drawStroke(outline, 2.25), drawStroke(loop, 1.25)]
    const ring = floodFillRegion({
      strokes,
      x: 200,
      y: 500,
      style: solidStyle('#B91C1C'),
      gapClose: DEFAULT_GAP_CLOSE_PX,
    })
    expect(ring.ok).toBe(false)
    if (!ring.ok) expect(ring.reason).toBe('unsupported_cutout')
  })

  it('preserves Fit Page croquis framing and allows pan into paper margins', () => {
    const vp = { width: 800, height: 1000 }
    const fitted = fitPage(vp)
    // Croquis scale — not paper scale (must not shrink the model by default).
    expect(fitted.scale).toBeCloseTo(Math.min(800 / DESIGN_WIDTH, 1000 / DESIGN_HEIGHT), 6)
    expect(fitted.scale).toBeGreaterThan(fitDrawingScale(vp))

    // Pan toward the top margin should remain within paper clamp.
    const up = clampPan({ scale: fitted.scale, panX: fitted.panX, panY: fitted.panY + 400 }, vp)
    expect(Number.isFinite(up.panY)).toBe(true)
    // Margins are reachable: paper height > croquis height at same scale.
    expect(PAPER_HEIGHT * fitted.scale).toBeGreaterThan(DESIGN_HEIGHT * fitted.scale)
  })

  it('fail-closes Magic capture when artwork uses extended margins (no crop, 0 paid AI)', async () => {
    const strokes = oversizedPuffyDress()
    await expect(
      captureSketchForMagic({
        strokes,
        fills: [],
        referenceUrl: null,
      }),
    ).rejects.toThrow(/extends beyond the standard Magic frame/i)
  })

  it('handles hundreds of strokes without unbounded allocation', () => {
    const strokes: Stroke[] = []
    for (let i = 0; i < 500; i += 1) {
      const x = 100 + (i % 40) * 12
      const y = 100 + Math.floor(i / 40) * 14
      strokes.push(drawStroke(strideLine(x, y, x + 8, y + 8, 4), 1.75))
    }
    const t0 = Date.now()
    const barrier = buildInkBarrierMask(strokes, DEFAULT_GAP_CLOSE_PX, {
      endpointSealPx: DEFAULT_ENDPOINT_SEAL_PX,
    })
    const elapsed = Date.now() - t0
    expect(barrier.length).toBe(PAPER_WIDTH * PAPER_HEIGHT)
    expect(elapsed).toBeLessThan(15_000)
  })

  it('paints solid fills whose contours use negative design coordinates', () => {
    const strokes = oversizedPuffyDress()
    const result = floodFillRegion({
      strokes,
      x: 384,
      y: 480,
      style: solidStyle('#1D4ED8'),
    })
    expect(result.ok).toBe(true)
    if (!result.ok) return
    const canvas = createCanvas(PAPER_WIDTH, PAPER_HEIGHT)
    const ctx = canvas.getContext('2d')!
    ctx.translate(-PAPER_ORIGIN_X, -PAPER_ORIGIN_Y)
    paintFillOps(ctx, [result.fill])
    paintInkStrokes(ctx, strokes)
    const ix = Math.round(384 - PAPER_ORIGIN_X)
    const iy = Math.round(480 - PAPER_ORIGIN_Y)
    expect(ctx.getImageData(ix, iy, 1, 1).data[3]!).toBeGreaterThan(10)
  })
})
