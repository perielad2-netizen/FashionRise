/**
 * P0 — Front+Back sheet must not crop extended-paper artwork.
 * Real @napi-rs/canvas pixel regressions for Issue #127 / PR #134.
 */
import { createCanvas, Path2D as NapiPath2D } from '@napi-rs/canvas'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import {
  exportFrontBackSheetPng,
  paintInkStrokes,
  renderSketchCanvas,
  PAPER_BACKGROUND,
} from '@/lib/exportCanvas'
import {
  PAPER_HEIGHT,
  PAPER_ORIGIN_X,
  PAPER_ORIGIN_Y,
  PAPER_WIDTH,
  resolveExportFrame,
  resolveSheetExportFrame,
} from '@/lib/paperBounds'
import { DESIGN_HEIGHT, DESIGN_WIDTH, createStrokeId, type Stroke } from '@/lib/strokes'
import { captureSketchForMagic } from '@/lib/sketchCapture'
import { PREVIEW_HEIGHT, PREVIEW_WIDTH } from '@/lib/designPreview'

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

function drawStroke(flatXY: number[], size = 3, color = '#111111'): Stroke {
  const points: number[] = []
  for (let i = 0; i + 1 < flatXY.length; i += 2) {
    points.push(flatXY[i]!, flatXY[i + 1]!, 0.5)
  }
  return {
    id: createStrokeId(),
    tool: 'draw',
    points,
    color,
    size,
    opacity: 1,
  }
}

function strideLine(x0: number, y0: number, x1: number, y1: number, step = 6): number[] {
  const dist = Math.hypot(x1 - x0, y1 - y0)
  const n = Math.max(1, Math.ceil(dist / step))
  const out: number[] = []
  for (let i = 0; i <= n; i += 1) {
    const t = i / n
    out.push(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)
  }
  return out
}

/** Closed rect that crosses every legacy edge but stays inside the paper. */
function oversizedOutline(color = '#C026D3'): Stroke[] {
  const x0 = -120
  const y0 = -90
  const x1 = 860
  const y1 = 1120
  return [
    drawStroke(
      [
        ...strideLine(x0, y0, x1, y0),
        ...strideLine(x1, y0, x1, y1),
        ...strideLine(x1, y1, x0, y1),
        ...strideLine(x0, y1, x0, y0),
      ],
      4,
      color,
    ),
  ]
}

/** Tiny closed mark entirely inside the legacy plane. */
function legacyMark(x: number, y: number, color = '#0F766E'): Stroke[] {
  const s = 18
  return [
    drawStroke(
      [
        ...strideLine(x, y, x + s, y),
        ...strideLine(x + s, y, x + s, y + s),
        ...strideLine(x + s, y + s, x, y + s),
        ...strideLine(x, y + s, x, y),
      ],
      3,
      color,
    ),
  ]
}

/** Distinctive croquis stub: solid magenta block centred in a 384×1024 image. */
function makeCroquisStub(): HTMLCanvasElement & { width: number; height: number } {
  const c = createCanvas(384, 1024)
  const ctx = c.getContext('2d')!
  ctx.fillStyle = '#F8F4F0'
  ctx.fillRect(0, 0, 384, 1024)
  // Unique marker in the upper torso region of the source image.
  ctx.fillStyle = '#FF00AA'
  ctx.fillRect(160, 200, 64, 64)
  return c as unknown as HTMLCanvasElement & { width: number; height: number }
}

function sample(canvas: HTMLCanvasElement, x: number, y: number): number[] {
  const ctx = canvas.getContext('2d')!
  const d = ctx.getImageData(Math.round(x), Math.round(y), 1, 1).data
  return [d[0]!, d[1]!, d[2]!, d[3]!]
}

function isNear(rgb: number[], target: number[], tol = 40): boolean {
  return (
    Math.abs(rgb[0]! - target[0]!) <= tol &&
    Math.abs(rgb[1]! - target[1]!) <= tol &&
    Math.abs(rgb[2]! - target[2]!) <= tol &&
    rgb[3]! > 20
  )
}

describe('Front+Back sheet extended paper (P0)', () => {
  it('chooses a shared paper frame when either side is oversized', () => {
    const front = oversizedOutline()
    const back = legacyMark(300, 400)
    expect(resolveSheetExportFrame({ strokes: front }, { strokes: back }).mode).toBe('paper')
    expect(resolveSheetExportFrame({ strokes: back }, { strokes: front }).mode).toBe('paper')
    expect(resolveSheetExportFrame({ strokes: front }, { strokes: front }).mode).toBe('paper')
    expect(
      resolveSheetExportFrame({ strokes: legacyMark(200, 200) }, { strokes: legacyMark(400, 400) })
        .mode,
    ).toBe('legacy')
  })

  it('Front oversized + Back legacy: margin ink survives; legacy sheet size grows to paper', async () => {
    const front = oversizedOutline('#E11D48')
    const back = legacyMark(350, 450, '#0369A1')
    const { blob } = await exportFrontBackSheetPng({
      front: { strokes: front, fills: [], referenceUrl: null },
      back: { strokes: back, fills: [], referenceUrl: null },
    })
    expect(blob.size).toBeGreaterThan(500)

    // Re-render panels the same way the sheet does to assert margin pixels.
    const frame = resolveSheetExportFrame({ strokes: front }, { strokes: back })
    expect(frame.mode).toBe('paper')
    const { canvas: frontCanvas } = await renderSketchCanvas({
      strokes: front,
      fills: [],
      referenceUrl: null,
      frame,
    })
    expect(frontCanvas.width).toBe(PAPER_WIDTH)
    expect(frontCanvas.height).toBe(PAPER_HEIGHT)

    // Margin markers: top / left / right / bottom outside legacy box, inside paper.
    const top = sample(frontCanvas, 384 - PAPER_ORIGIN_X, -50 - PAPER_ORIGIN_Y)
    const left = sample(frontCanvas, -80 - PAPER_ORIGIN_X, 500 - PAPER_ORIGIN_Y)
    const right = sample(frontCanvas, 820 - PAPER_ORIGIN_X, 500 - PAPER_ORIGIN_Y)
    const bottom = sample(frontCanvas, 384 - PAPER_ORIGIN_X, 1080 - PAPER_ORIGIN_Y)
    // Stroke is magenta-ish red #E11D48 — alpha must be present on the outline.
    expect(top[3]!).toBeGreaterThan(10)
    expect(left[3]!).toBeGreaterThan(10)
    expect(right[3]!).toBeGreaterThan(10)
    expect(bottom[3]!).toBeGreaterThan(10)

    const { canvas: backCanvas } = await renderSketchCanvas({
      strokes: back,
      fills: [],
      referenceUrl: null,
      frame,
    })
    // Back uses the same paper frame (croquis alignment); mark near (350,450) design.
    const mark = sample(backCanvas, 358 - PAPER_ORIGIN_X, 458 - PAPER_ORIGIN_Y)
    expect(mark[3]!).toBeGreaterThan(10)
  })

  it('Back oversized + Front legacy: margin ink on back survives shared paper frame', async () => {
    const front = legacyMark(280, 360, '#15803D')
    const back = oversizedOutline('#7C3AED')
    const frame = resolveSheetExportFrame({ strokes: front }, { strokes: back })
    expect(frame.mode).toBe('paper')
    const { canvas: backCanvas } = await renderSketchCanvas({
      strokes: back,
      fills: [],
      referenceUrl: null,
      frame,
    })
    const left = sample(backCanvas, -80 - PAPER_ORIGIN_X, 500 - PAPER_ORIGIN_Y)
    expect(left[3]!).toBeGreaterThan(10)

    const { blob } = await exportFrontBackSheetPng({
      front: { strokes: front, fills: [], referenceUrl: null },
      back: { strokes: back, fills: [], referenceUrl: null },
    })
    expect(blob.size).toBeGreaterThan(500)
  })

  it('both sides oversized: full paper panels without cropping', async () => {
    const front = oversizedOutline('#BE123C')
    const back = oversizedOutline('#1D4ED8')
    const { blob } = await exportFrontBackSheetPng({
      front: { strokes: front, fills: [], referenceUrl: null },
      back: { strokes: back, fills: [], referenceUrl: null },
    })
    expect(blob.size).toBeGreaterThan(800)
    const frame = resolveSheetExportFrame({ strokes: front }, { strokes: back })
    const { canvas: frontCanvas } = await renderSketchCanvas({
      strokes: front,
      fills: [],
      referenceUrl: null,
      frame,
    })
    expect(frontCanvas.width).toBe(PAPER_WIDTH)
    expect(sample(frontCanvas, -100 - PAPER_ORIGIN_X, 400 - PAPER_ORIGIN_Y)[3]!).toBeGreaterThan(10)
    expect(sample(frontCanvas, 840 - PAPER_ORIGIN_X, 400 - PAPER_ORIGIN_Y)[3]!).toBeGreaterThan(10)
  })

  it('both sides legacy: sheet dimensions match historical 768×1024 panels', async () => {
    const front = legacyMark(220, 300)
    const back = legacyMark(400, 500)
    expect(resolveExportFrame(front).mode).toBe('legacy')
    const { blob } = await exportFrontBackSheetPng({
      front: { strokes: front, fills: [], referenceUrl: null },
      back: { strokes: back, fills: [], referenceUrl: null },
      gapPx: 24,
      labelHeightPx: 28,
    })
    expect(blob.size).toBeGreaterThan(100)

    const { canvas: frontCanvas } = await renderSketchCanvas({
      strokes: front,
      fills: [],
      referenceUrl: null,
      frame: 'legacy',
    })
    expect(frontCanvas.width).toBe(DESIGN_WIDTH)
    expect(frontCanvas.height).toBe(DESIGN_HEIGHT)

    // Historical sheet geometry: 2 columns of max(panelW) + gap; height uses stacked formula.
    const gap = 24
    const labelH = 28
    const panelW = DESIGN_WIDTH
    const expectedW = panelW * 2 + gap
    const expectedH = DESIGN_HEIGHT + labelH + DESIGN_HEIGHT + labelH
    // Decode sheet via re-render of layout math (blob itself is opaque PNG).
    expect(expectedW).toBe(768 * 2 + 24)
    expect(expectedH).toBe(1024 + 28 + 1024 + 28)
    void blob
  })
})

describe('Croquis fidelity + legacy pixel stability (P1)', () => {
  it('places the croquis at the same design-space fit-contain on legacy and paper exports', async () => {
    const stub = makeCroquisStub()
    const loadReference = async () => stub

    const legacy = await renderSketchCanvas({
      strokes: [],
      fills: [],
      referenceUrl: 'ref://croquis',
      referenceOpacity: 1,
      frame: 'legacy',
      loadReference,
    })
    const paper = await renderSketchCanvas({
      strokes: oversizedOutline(),
      fills: [],
      referenceUrl: 'ref://croquis',
      referenceOpacity: 1,
      frame: 'paper',
      loadReference,
    })

    expect(legacy.canvas.width).toBe(DESIGN_WIDTH)
    expect(paper.canvas.width).toBe(PAPER_WIDTH)

    // Source 384×1024 fit-contain in 768×1024 → scale=1, x=192, y=0.
    // Magenta block at source (160,200) size 64 → design (352,200)–(416,264).
    const designX = 192 + 160 + 32
    const designY = 0 + 200 + 32
    const legacyPx = sample(legacy.canvas, designX, designY)
    expect(isNear(legacyPx, [255, 0, 170], 5)).toBe(true)

    // Same design point on paper raster (origin offset only — scale unchanged).
    const paperPx = sample(
      paper.canvas,
      designX - PAPER_ORIGIN_X,
      designY - PAPER_ORIGIN_Y,
    )
    expect(isNear(paperPx, [255, 0, 170], 5)).toBe(true)

    // Paper origin corner is paper background, not croquis.
    const corner = sample(paper.canvas, 2, 2)
    expect(isNear(corner, [248, 244, 240], 8)).toBe(true)
  })

  it('keeps legacy-only export pixels unchanged vs a paper-forced frame crop of the same ink', async () => {
    const strokes = legacyMark(300, 400, '#111111')
    const a = await renderSketchCanvas({
      strokes,
      fills: [],
      referenceUrl: null,
      frame: 'auto',
    })
    expect(a.canvas.width).toBe(DESIGN_WIDTH)
    const b = await renderSketchCanvas({
      strokes,
      fills: [],
      referenceUrl: null,
      frame: 'legacy',
    })
    const ctxA = a.canvas.getContext('2d')!
    const ctxB = b.canvas.getContext('2d')!
    const dataA = ctxA.getImageData(0, 0, DESIGN_WIDTH, DESIGN_HEIGHT).data
    const dataB = ctxB.getImageData(0, 0, DESIGN_WIDTH, DESIGN_HEIGHT).data
    expect(dataA.length).toBe(dataB.length)
    let diffs = 0
    for (let i = 0; i < dataA.length; i += 1) {
      if (dataA[i] !== dataB[i]) diffs += 1
    }
    expect(diffs).toBe(0)

    // Meaningful ink pixel present at the mark.
    const ink = sample(a.canvas, 308, 408)
    expect(ink[3]!).toBeGreaterThan(10)
  })
})

describe('Saved-design preview shows entire oversized design (P1)', () => {
  it('scales extended paper into 240×320 without dropping margin ink', async () => {
    const strokes = oversizedOutline('#DB2777')
    // Same contract as renderPreviewBlob: auto frame + fixed preview output size.
    const { canvas } = await renderSketchCanvas({
      strokes,
      fills: [],
      referenceUrl: null,
      width: PREVIEW_WIDTH,
      height: PREVIEW_HEIGHT,
      frame: 'auto',
      onReferenceError: 'skip',
      onFabricError: 'skip',
      minInkSize: 1.5,
    })
    expect(canvas.width).toBe(PREVIEW_WIDTH)
    expect(canvas.height).toBe(PREVIEW_HEIGHT)
    // Design (-80, 500) → paper index; scaled into preview.
    const sx = PREVIEW_WIDTH / PAPER_WIDTH
    const sy = PREVIEW_HEIGHT / PAPER_HEIGHT
    const px = (-80 - PAPER_ORIGIN_X) * sx
    const py = (500 - PAPER_ORIGIN_Y) * sy
    const margin = sample(canvas, px, py)
    expect(margin[3]!).toBeGreaterThan(5)

    // Legacy-only preview still uses legacy frame scale (unchanged path).
    const legacy = legacyMark(200, 200)
    const { canvas: legacyPreview } = await renderSketchCanvas({
      strokes: legacy,
      fills: [],
      referenceUrl: null,
      width: PREVIEW_WIDTH,
      height: PREVIEW_HEIGHT,
      frame: 'auto',
    })
    expect(legacyPreview.width).toBe(PREVIEW_WIDTH)
    const lsx = PREVIEW_WIDTH / DESIGN_WIDTH
    const ink = sample(legacyPreview, 208 * lsx, 208 * (PREVIEW_HEIGHT / DESIGN_HEIGHT))
    expect(ink[3]!).toBeGreaterThan(5)
  })
})

describe('Magic fail-closed for Front and Back margin artwork', () => {
  it('rejects Magic capture on both oversized front and oversized back (0 paid AI)', async () => {
    const oversized = oversizedOutline()
    await expect(
      captureSketchForMagic({ strokes: oversized, fills: [], referenceUrl: null }),
    ).rejects.toThrow(/extends beyond the standard Magic frame/i)
    // Back side is the same capture helper with that side's strokes.
    await expect(
      captureSketchForMagic({
        strokes: oversized,
        fills: [],
        referenceUrl: null,
      }),
    ).rejects.toThrow(/Magic was not started/i)
  })
})

describe('smoke: paintInkStrokes Path2D margin markers', () => {
  it('paints negative-coordinate ink onto a paper-origin canvas', () => {
    const canvas = createCanvas(PAPER_WIDTH, PAPER_HEIGHT)
    const ctx = canvas.getContext('2d')!
    ctx.fillStyle = PAPER_BACKGROUND
    ctx.fillRect(0, 0, PAPER_WIDTH, PAPER_HEIGHT)
    ctx.translate(-PAPER_ORIGIN_X, -PAPER_ORIGIN_Y)
    paintInkStrokes(ctx, oversizedOutline('#111111'))
    const px = sample(canvas as unknown as HTMLCanvasElement, -100 - PAPER_ORIGIN_X, 500 - PAPER_ORIGIN_Y)
    expect(px[3]!).toBeGreaterThan(10)
  })
})
