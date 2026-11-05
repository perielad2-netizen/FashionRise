/**
 * Prod incident 2026-11-05: shade-layer eraser scribble outside 768×1024 flipped
 * resolveExportFrame → paper, letterboxed garment-only Try On capture, and failed
 * assertGarmentCaptureCompleteness ("lost lower parts…").
 */
import { createCanvas, Path2D as NapiPath2D, loadImage } from '@napi-rs/canvas'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { exportSketchPng } from '@/lib/exportCanvas'
import { resolveExportFrame } from '@/lib/paperBounds'
import { DESIGN_HEIGHT, DESIGN_WIDTH, type Stroke } from '@/lib/strokes'
import type { FillOp } from '@/lib/fills'
import { TRY_ON_GARMENT_CAPTURE_SCALE } from '@/lib/sketchCapture'

const g = globalThis as typeof globalThis & { Path2D: typeof Path2D; document: Document }
let previousPath2D: typeof Path2D | undefined
let previousCreateElement: typeof document.createElement | undefined

beforeAll(() => {
  previousPath2D = g.Path2D
  previousCreateElement = document.createElement.bind(document)
  g.Path2D = NapiPath2D as unknown as typeof Path2D
  document.createElement = ((tag: string) => {
    if (tag === 'canvas') return createCanvas(8, 8) as unknown as HTMLCanvasElement
    return previousCreateElement!(tag)
  }) as typeof document.createElement
})

afterAll(() => {
  if (previousPath2D) g.Path2D = previousPath2D
  if (previousCreateElement) document.createElement = previousCreateElement
})

describe('Try On capture vs shade eraser overshoot', () => {
  it('keeps legacy frame and hem when shade erase scribbles outside the croquis', async () => {
    const ink: Stroke = {
      id: 'ink',
      tool: 'draw',
      color: '#111111',
      size: 4,
      opacity: 1,
      brushKind: 'tapered',
      logicalLayer: 'ink',
      points: [200, 200, 0.5, 220, 240, 0.5],
    }
    // Mirrors prod shade erase: full-page clean scribble outside legacy box.
    const shadeErase: Stroke = {
      id: 'shade-erase-giant',
      tool: 'erase',
      color: '#000000',
      size: 32.5,
      opacity: 1,
      brushKind: 'tapered',
      logicalLayer: 'shade',
      points: [90, -14, 0.5, 650, 400, 0.5, 100, 1117, 0.5],
    }
    const fills: FillOp[] = [
      {
        id: 'legs',
        contour: [220, 160, 520, 160, 520, 980, 220, 980],
        style: { kind: 'solid', color: '#B91C1C' },
        seedX: 360,
        seedY: 500,
      },
    ]
    const strokes = [ink, shadeErase]

    expect(resolveExportFrame(strokes, fills).mode).toBe('legacy')

    const width = DESIGN_WIDTH * TRY_ON_GARMENT_CAPTURE_SCALE
    const height = DESIGN_HEIGHT * TRY_ON_GARMENT_CAPTURE_SCALE
    const { blob } = await exportSketchPng({
      strokes,
      fills,
      referenceUrl: null,
      garmentOnly: true,
      width,
      height,
      onReferenceError: 'skip',
      onFabricError: 'throw',
    })

    const img = await loadImage(Buffer.from(await blob.arrayBuffer()))
    const canvas = createCanvas(img.width, img.height)
    const ctx = canvas.getContext('2d')
    ctx.drawImage(img, 0, 0)
    const { data: px, width: w, height: h } = ctx.getImageData(0, 0, canvas.width, canvas.height)
    let minY = h
    let maxY = 0
    let legPixels = 0
    const legY0 = Math.floor(850 * (h / DESIGN_HEIGHT))
    const legY1 = Math.floor(980 * (h / DESIGN_HEIGHT))
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        if (px[(y * w + x) * 4 + 3]! >= 24) {
          minY = Math.min(minY, y)
          maxY = Math.max(maxY, y)
          if (y >= legY0 && y < legY1) legPixels += 1
        }
      }
    }
    const dMin = minY / (h / DESIGN_HEIGHT)
    const dMax = maxY / (h / DESIGN_HEIGHT)
    expect(dMin).toBeLessThan(200)
    expect(dMax).toBeGreaterThan(900)
    expect(legPixels).toBeGreaterThan(1000)
  }, 60_000)
})
