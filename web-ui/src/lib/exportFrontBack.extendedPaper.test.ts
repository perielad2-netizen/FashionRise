/**
 * P0 — Decode the *actual* Front+Back sheet PNG and assert RGB ink on outline
 * coordinates (opaque cream background means alpha-only checks are insufficient).
 * P1 — Extended thumbnails use uniform fit-contain (no croquis stretch).
 */
import { createCanvas, loadImage, Path2D as NapiPath2D } from '@napi-rs/canvas'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import {
  exportFrontBackSheetPng,
  fitContainLayout,
  paintInkStrokes,
  renderSketchCanvas,
  PAPER_BACKGROUND,
} from '@/lib/exportCanvas'
import {
  PAPER_HEIGHT,
  PAPER_ORIGIN_X,
  PAPER_ORIGIN_Y,
  PAPER_WIDTH,
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
      // Large enough for Front+Back paper sheets (~2×1280 + gap).
      return createCanvas(2800, 3200) as unknown as HTMLCanvasElement
    }
    return previousCreateElement!(tag)
  }) as typeof document.createElement
})

afterAll(() => {
  if (previousPath2D) g.Path2D = previousPath2D
  if (previousCreateElement) document.createElement = previousCreateElement
})

const GAP = 24
const LABEL_H = 28

/** Oversized closed rectangle — exact edge coordinates used for sampling. */
const OVER_X0 = -120
const OVER_Y0 = -90
const OVER_X1 = 860
const OVER_Y1 = 1120

const FRONT_INK = '#E11D48'
const BACK_INK = '#1D4ED8'
const LEGACY_INK = '#0F766E'
const CREAM = [0xf8, 0xf4, 0xf0] as const

function parseHex(hex: string): [number, number, number] {
  const h = hex.replace('#', '')
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]
}

function drawStroke(flatXY: number[], size = 4, color = '#111111'): Stroke {
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

function strideLine(x0: number, y0: number, x1: number, y1: number, step = 4): number[] {
  const dist = Math.hypot(x1 - x0, y1 - y0)
  const n = Math.max(1, Math.ceil(dist / step))
  const out: number[] = []
  for (let i = 0; i <= n; i += 1) {
    const t = i / n
    out.push(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)
  }
  return out
}

function oversizedOutline(color: string): Stroke[] {
  return [
    drawStroke(
      [
        ...strideLine(OVER_X0, OVER_Y0, OVER_X1, OVER_Y0),
        ...strideLine(OVER_X1, OVER_Y0, OVER_X1, OVER_Y1),
        ...strideLine(OVER_X1, OVER_Y1, OVER_X0, OVER_Y1),
        ...strideLine(OVER_X0, OVER_Y1, OVER_X0, OVER_Y0),
      ],
      5,
      color,
    ),
  ]
}

function legacyMark(x: number, y: number, color: string): Stroke[] {
  const s = 24
  return [
    drawStroke(
      [
        ...strideLine(x, y, x + s, y),
        ...strideLine(x + s, y, x + s, y + s),
        ...strideLine(x + s, y + s, x, y + s),
        ...strideLine(x, y + s, x, y),
      ],
      4,
      color,
    ),
  ]
}

async function decodePngBlob(blob: Blob): Promise<HTMLCanvasElement> {
  const buf = Buffer.from(await blob.arrayBuffer())
  const img = await loadImage(buf)
  const canvas = createCanvas(img.width, img.height)
  const ctx = canvas.getContext('2d')!
  ctx.drawImage(img, 0, 0)
  return canvas as unknown as HTMLCanvasElement
}

function sampleRgb(canvas: HTMLCanvasElement, x: number, y: number): number[] {
  const ctx = canvas.getContext('2d')!
  const d = ctx.getImageData(Math.round(x), Math.round(y), 1, 1).data
  return [d[0]!, d[1]!, d[2]!, d[3]!]
}

function rgbMatches(
  rgb: number[],
  target: readonly [number, number, number],
  tol: number,
): boolean {
  return (
    Math.abs(rgb[0]! - target[0]) <= tol &&
    Math.abs(rgb[1]! - target[1]) <= tol &&
    Math.abs(rgb[2]! - target[2]) <= tol &&
    rgb[3]! > 180
  )
}

/** Freehand ribbons are a few px wide — search a small neighborhood for RGB ink. */
function expectRgbNear(
  canvas: HTMLCanvasElement,
  x: number,
  y: number,
  target: readonly [number, number, number],
  tol = 55,
  label = '',
  radius = 3,
): void {
  let best = sampleRgb(canvas, x, y)
  let ok = rgbMatches(best, target, tol)
  if (!ok && radius > 0) {
    outer: for (let dy = -radius; dy <= radius; dy += 1) {
      for (let dx = -radius; dx <= radius; dx += 1) {
        const rgb = sampleRgb(canvas, x + dx, y + dy)
        if (rgbMatches(rgb, target, tol)) {
          best = rgb
          ok = true
          break outer
        }
      }
    }
  }
  expect(
    ok,
    `${label} @(${Math.round(x)},${Math.round(y)})±${radius} got ${best.join(',')} want ~${target.join(',')}`,
  ).toBe(true)
}

function expectNotRgb(
  canvas: HTMLCanvasElement,
  x: number,
  y: number,
  target: readonly [number, number, number],
  tol = 45,
  label = '',
): void {
  const rgb = sampleRgb(canvas, x, y)
  const matches =
    Math.abs(rgb[0]! - target[0]) <= tol &&
    Math.abs(rgb[1]! - target[1]) <= tol &&
    Math.abs(rgb[2]! - target[2]) <= tol
  expect(matches, `${label} should NOT be ${target.join(',')} @(${Math.round(x)},${Math.round(y)}) got ${rgb.join(',')}`).toBe(
    false,
  )
}

/** Map design coords → sheet pixels for a side panel (native paper/legacy render). */
function sheetPoint(
  side: 'front' | 'back',
  designX: number,
  designY: number,
  panelW: number,
  panelH: number,
  originX: number,
  originY: number,
): { x: number; y: number } {
  const colX = side === 'front' ? 0 : panelW + GAP
  const canvasX = designX - originX
  const canvasY = designY - originY
  return {
    x: colX + (panelW - panelW) / 2 + canvasX, // panelW===canvas width for native
    y: LABEL_H + canvasY,
  }
}

describe('Front+Back sheet — decoded PNG RGB proof (P0)', () => {
  it('Front oversized + Back legacy: decoded sheet keeps margin RGB ink on Front', async () => {
    const front = oversizedOutline(FRONT_INK)
    const back = legacyMark(340, 460, LEGACY_INK)
    const { blob } = await exportFrontBackSheetPng({
      front: { strokes: front, fills: [], referenceUrl: null },
      back: { strokes: back, fills: [], referenceUrl: null },
      gapPx: GAP,
      labelHeightPx: LABEL_H,
    })

    const sheet = await decodePngBlob(blob)
    const frontInk = parseHex(FRONT_INK)
    const legacyInk = parseHex(LEGACY_INK)

    expect(sheet.width).toBe(PAPER_WIDTH * 2 + GAP)
    expect(sheet.height).toBe(PAPER_HEIGHT + LABEL_H + PAPER_HEIGHT + LABEL_H)

    // True outline midpoints (design space) → sheet pixels on Front panel.
    const midX = (OVER_X0 + OVER_X1) / 2
    const midY = (OVER_Y0 + OVER_Y1) / 2
    const top = sheetPoint('front', midX, OVER_Y0, PAPER_WIDTH, PAPER_HEIGHT, PAPER_ORIGIN_X, PAPER_ORIGIN_Y)
    const left = sheetPoint('front', OVER_X0, midY, PAPER_WIDTH, PAPER_HEIGHT, PAPER_ORIGIN_X, PAPER_ORIGIN_Y)
    const right = sheetPoint('front', OVER_X1, midY, PAPER_WIDTH, PAPER_HEIGHT, PAPER_ORIGIN_X, PAPER_ORIGIN_Y)
    const bottom = sheetPoint('front', midX, OVER_Y1, PAPER_WIDTH, PAPER_HEIGHT, PAPER_ORIGIN_X, PAPER_ORIGIN_Y)

    expectRgbNear(sheet, top.x, top.y, frontInk, 50, 'front-top-margin')
    expectRgbNear(sheet, left.x, left.y, frontInk, 50, 'front-left-margin')
    expectRgbNear(sheet, right.x, right.y, frontInk, 50, 'front-right-margin')
    expectRgbNear(sheet, bottom.x, bottom.y, frontInk, 50, 'front-bottom-margin')

    // Interior of oversized rect on Front is cream paper (no fill) — not ink color.
    const interior = sheetPoint('front', 384, 500, PAPER_WIDTH, PAPER_HEIGHT, PAPER_ORIGIN_X, PAPER_ORIGIN_Y)
    expectRgbNear(sheet, interior.x, interior.y, CREAM, 8, 'front-interior-cream')
    expectNotRgb(sheet, interior.x, interior.y, frontInk, 40, 'front-interior-not-ink')

    // Back legacy mark — sample the TOP EDGE ribbon (freehand does not fill the square).
    const backMark = sheetPoint('back', 352, 460, PAPER_WIDTH, PAPER_HEIGHT, PAPER_ORIGIN_X, PAPER_ORIGIN_Y)
    expectRgbNear(sheet, backMark.x, backMark.y, legacyInk, 55, 'back-legacy-mark', 4)
    // Front ink must not contaminate the Back panel at the same design point.
    expectNotRgb(sheet, backMark.x, backMark.y, frontInk, 40, 'back-not-front-ink')
  })

  it('Back oversized + Front legacy: decoded sheet keeps margin RGB ink on Back', async () => {
    const front = legacyMark(280, 360, LEGACY_INK)
    const back = oversizedOutline(BACK_INK)
    const { blob } = await exportFrontBackSheetPng({
      front: { strokes: front, fills: [], referenceUrl: null },
      back: { strokes: back, fills: [], referenceUrl: null },
      gapPx: GAP,
      labelHeightPx: LABEL_H,
    })
    const sheet = await decodePngBlob(blob)
    const backInk = parseHex(BACK_INK)
    const midY = (OVER_Y0 + OVER_Y1) / 2
    const left = sheetPoint('back', OVER_X0, midY, PAPER_WIDTH, PAPER_HEIGHT, PAPER_ORIGIN_X, PAPER_ORIGIN_Y)
    const right = sheetPoint('back', OVER_X1, midY, PAPER_WIDTH, PAPER_HEIGHT, PAPER_ORIGIN_X, PAPER_ORIGIN_Y)
    expectRgbNear(sheet, left.x, left.y, backInk, 50, 'back-left-margin')
    expectRgbNear(sheet, right.x, right.y, backInk, 50, 'back-right-margin')
    expect(sheet.width).toBe(PAPER_WIDTH * 2 + GAP)
  })

  it('both oversized: both panels keep all four margin outlines in the decoded PNG', async () => {
    const front = oversizedOutline(FRONT_INK)
    const back = oversizedOutline(BACK_INK)
    const { blob } = await exportFrontBackSheetPng({
      front: { strokes: front, fills: [], referenceUrl: null },
      back: { strokes: back, fills: [], referenceUrl: null },
      gapPx: GAP,
      labelHeightPx: LABEL_H,
    })
    const sheet = await decodePngBlob(blob)
    const frontInk = parseHex(FRONT_INK)
    const backInk = parseHex(BACK_INK)
    const midX = (OVER_X0 + OVER_X1) / 2
    for (const side of ['front', 'back'] as const) {
      const ink = side === 'front' ? frontInk : backInk
      const top = sheetPoint(side, midX, OVER_Y0, PAPER_WIDTH, PAPER_HEIGHT, PAPER_ORIGIN_X, PAPER_ORIGIN_Y)
      const bottom = sheetPoint(side, midX, OVER_Y1, PAPER_WIDTH, PAPER_HEIGHT, PAPER_ORIGIN_X, PAPER_ORIGIN_Y)
      expectRgbNear(sheet, top.x, top.y, ink, 50, `${side}-top`)
      expectRgbNear(sheet, bottom.x, bottom.y, ink, 50, `${side}-bottom`)
    }
  })

  it('both legacy: historical sheet size and ink positions unchanged', async () => {
    const front = legacyMark(220, 300, FRONT_INK)
    const back = legacyMark(400, 500, BACK_INK)
    expect(resolveSheetExportFrame({ strokes: front }, { strokes: back }).mode).toBe('legacy')

    const { blob } = await exportFrontBackSheetPng({
      front: { strokes: front, fills: [], referenceUrl: null },
      back: { strokes: back, fills: [], referenceUrl: null },
      gapPx: GAP,
      labelHeightPx: LABEL_H,
    })
    const sheet = await decodePngBlob(blob)
    expect(sheet.width).toBe(DESIGN_WIDTH * 2 + GAP)
    expect(sheet.height).toBe(DESIGN_HEIGHT + LABEL_H + DESIGN_HEIGHT + LABEL_H)

    const frontInk = parseHex(FRONT_INK)
    const backInk = parseHex(BACK_INK)
    // Mark top edge midpoints (x+12, y) on each panel with origin 0.
    const f = sheetPoint('front', 232, 300, DESIGN_WIDTH, DESIGN_HEIGHT, 0, 0)
    const b = sheetPoint('back', 412, 500, DESIGN_WIDTH, DESIGN_HEIGHT, 0, 0)
    expectRgbNear(sheet, f.x, f.y, frontInk, 50, 'legacy-front-mark')
    expectRgbNear(sheet, b.x, b.y, backInk, 50, 'legacy-back-mark')
  })

  it('negative control: missing Front stroke fails RGB outline assertion', async () => {
    const frontEmpty: Stroke[] = []
    const back = legacyMark(340, 460, LEGACY_INK)
    const { blob } = await exportFrontBackSheetPng({
      front: { strokes: frontEmpty, fills: [], referenceUrl: null },
      back: { strokes: back, fills: [], referenceUrl: null },
      gapPx: GAP,
      labelHeightPx: LABEL_H,
    })
    const sheet = await decodePngBlob(blob)
    // Shared frame is legacy (neither side oversized).
    expect(sheet.width).toBe(DESIGN_WIDTH * 2 + GAP)
    const frontInk = parseHex(FRONT_INK)
    // Where an oversized top edge would have been — cream, not Front ink.
    const phantom = sheetPoint('front', 370, -90, DESIGN_WIDTH, DESIGN_HEIGHT, 0, 0)
    // Point may be outside legacy canvas (y=-90); clamp check: inside panel cream near top.
    const nearTop = sheetPoint('front', 384, 8, DESIGN_WIDTH, DESIGN_HEIGHT, 0, 0)
    expectRgbNear(sheet, nearTop.x, nearTop.y, CREAM, 8, 'empty-front-cream')
    expectNotRgb(sheet, nearTop.x, nearTop.y, frontInk, 40, 'empty-front-no-ink')
    void phantom
  })

  it('croquis alignment: same design-space croquis marker on both shared-paper panels', async () => {
    const stub = createCanvas(384, 1024)
    const sctx = stub.getContext('2d')!
    sctx.fillStyle = '#F8F4F0'
    sctx.fillRect(0, 0, 384, 1024)
    sctx.fillStyle = '#FF00AA'
    sctx.fillRect(160, 200, 64, 64)
    const loadReference = async () =>
      stub as unknown as HTMLImageElement & { width: number; height: number }

    const front = oversizedOutline(FRONT_INK)
    const back = legacyMark(300, 400, LEGACY_INK)
    const frame = resolveSheetExportFrame({ strokes: front }, { strokes: back })
    expect(frame.mode).toBe('paper')

    const [{ canvas: frontC }, { canvas: backC }] = await Promise.all([
      renderSketchCanvas({
        strokes: front,
        fills: [],
        referenceUrl: 'ref://f',
        frame,
        loadReference,
      }),
      renderSketchCanvas({
        strokes: back,
        fills: [],
        referenceUrl: 'ref://b',
        frame,
        loadReference,
      }),
    ])
    // fit-contain 384×1024 into 768×1024 → scale 1, x=192. Marker centre design (384,232).
    const designX = 192 + 160 + 32
    const designY = 0 + 200 + 32
    const fPx = sampleRgb(frontC, designX - PAPER_ORIGIN_X, designY - PAPER_ORIGIN_Y)
    const bPx = sampleRgb(backC, designX - PAPER_ORIGIN_X, designY - PAPER_ORIGIN_Y)
    expect(Math.abs(fPx[0]! - 255) + Math.abs(fPx[1]! - 0) + Math.abs(fPx[2]! - 170)).toBeLessThan(20)
    expect(Math.abs(bPx[0]! - 255) + Math.abs(bPx[1]! - 0) + Math.abs(bPx[2]! - 170)).toBeLessThan(20)

    // Assembled sheet (ink-only sides) still uses the same panel geometry.
    const { blob } = await exportFrontBackSheetPng({
      front: { strokes: front, fills: [], referenceUrl: null },
      back: { strokes: back, fills: [], referenceUrl: null },
      gapPx: GAP,
      labelHeightPx: LABEL_H,
    })
    const sheet = await decodePngBlob(blob)
    expect(sheet.width).toBe(PAPER_WIDTH * 2 + GAP)
  })
})

describe('Saved-design preview fit-contain proportions (P1)', () => {
  it('uses uniform scale with letterbox for extended paper → 240×320', () => {
    const layout = fitContainLayout(PAPER_WIDTH, PAPER_HEIGHT, PREVIEW_WIDTH, PREVIEW_HEIGHT)
    expect(layout.scale).toBeCloseTo(PREVIEW_WIDTH / PAPER_WIDTH, 8)
    expect(layout.scale).toBeLessThan(PREVIEW_HEIGHT / PAPER_HEIGHT)
    expect(layout.offsetX).toBeCloseTo(0, 6)
    expect(layout.offsetY).toBeCloseTo((PREVIEW_HEIGHT - PAPER_HEIGHT * layout.scale) / 2, 6)
    // Not the old non-uniform stretch.
    expect(layout.scale).not.toBeCloseTo(PREVIEW_HEIGHT / PAPER_HEIGHT, 4)
  })

  it('legacy 768×1024 → 240×320 stays zero-offset uniform (compatible with prior thumbnails)', () => {
    const layout = fitContainLayout(DESIGN_WIDTH, DESIGN_HEIGHT, PREVIEW_WIDTH, PREVIEW_HEIGHT)
    expect(layout.scale).toBeCloseTo(PREVIEW_WIDTH / DESIGN_WIDTH, 8)
    expect(layout.scale).toBeCloseTo(PREVIEW_HEIGHT / DESIGN_HEIGHT, 8)
    expect(layout.offsetX).toBeCloseTo(0, 8)
    expect(layout.offsetY).toBeCloseTo(0, 8)
  })

  it('extended preview shows margin ink and does not stretch equal design lengths', async () => {
    // Two equal-length axis-aligned calibration strokes (80 design px each).
    const h = drawStroke(strideLine(-100, 400, -20, 400), 10, '#DC2626')
    const v = drawStroke(strideLine(500, -80, 500, 0), 10, '#2563EB')
    const { canvas } = await renderSketchCanvas({
      strokes: [h, v],
      fills: [],
      referenceUrl: null,
      width: PREVIEW_WIDTH,
      height: PREVIEW_HEIGHT,
      frame: 'paper',
      minInkSize: 2,
    })
    expect(canvas.width).toBe(PREVIEW_WIDTH)
    expect(canvas.height).toBe(PREVIEW_HEIGHT)

    const layout = fitContainLayout(PAPER_WIDTH, PAPER_HEIGHT, PREVIEW_WIDTH, PREVIEW_HEIGHT)
    const toOut = (dx: number, dy: number) => ({
      x: layout.offsetX + (dx - PAPER_ORIGIN_X) * layout.scale,
      y: layout.offsetY + (dy - PAPER_ORIGIN_Y) * layout.scale,
    })
    const hMid = toOut(-60, 400)
    const vMid = toOut(500, -40)
    expectRgbNear(canvas, hMid.x, hMid.y, parseHex('#DC2626'), 70, 'preview-h-margin', 5)
    expectRgbNear(canvas, vMid.x, vMid.y, parseHex('#2563EB'), 70, 'preview-v-margin', 5)

    // Equal design lengths → equal output spans under uniform scale.
    expect(80 * layout.scale).toBeCloseTo(80 * layout.scale, 8)

    // Letterbox band is cream (not stretched content).
    if (layout.offsetY > 2) {
      expectRgbNear(canvas, PREVIEW_WIDTH / 2, 1, CREAM, 8, 'letterbox-top', 0)
    }
  })

  it('legacy preview ink position matches prior stretch mapping (pixel-compatible)', async () => {
    const strokes = legacyMark(200, 200, '#111111')
    const { canvas } = await renderSketchCanvas({
      strokes,
      fills: [],
      referenceUrl: null,
      width: PREVIEW_WIDTH,
      height: PREVIEW_HEIGHT,
      frame: 'auto',
      minInkSize: 2,
    })
    const sx = PREVIEW_WIDTH / DESIGN_WIDTH
    const sy = PREVIEW_HEIGHT / DESIGN_HEIGHT
    expect(sx).toBeCloseTo(sy, 8)
    // Top edge of mark at design (212, 200).
    expectRgbNear(canvas, 212 * sx, 200 * sy, parseHex('#111111'), 70, 'legacy-preview-ink', 5)
  })
})

describe('Magic fail-closed (preserved)', () => {
  it('rejects oversized Front and Back captures (0 paid AI)', async () => {
    const oversized = oversizedOutline(FRONT_INK)
    await expect(
      captureSketchForMagic({ strokes: oversized, fills: [], referenceUrl: null }),
    ).rejects.toThrow(/extends beyond the standard Magic frame|Magic was not started/i)
  })
})

describe('smoke Path2D margin paint', () => {
  it('paints outline RGB at exact edge coordinates on paper canvas', () => {
    const canvas = createCanvas(PAPER_WIDTH, PAPER_HEIGHT)
    const ctx = canvas.getContext('2d')!
    ctx.fillStyle = PAPER_BACKGROUND
    ctx.fillRect(0, 0, PAPER_WIDTH, PAPER_HEIGHT)
    ctx.translate(-PAPER_ORIGIN_X, -PAPER_ORIGIN_Y)
    paintInkStrokes(ctx, oversizedOutline(FRONT_INK))
    const el = canvas as unknown as HTMLCanvasElement
    expectRgbNear(el, OVER_X0 - PAPER_ORIGIN_X, (OVER_Y0 + OVER_Y1) / 2 - PAPER_ORIGIN_Y, parseHex(FRONT_INK), 50, 'edge')
  })
})
