import { compositeFillAndInkLayers } from '@/lib/exportCanvas'
import type { FillOp } from '@/lib/fills'
import { DESIGN_HEIGHT, DESIGN_WIDTH, type Stroke } from '@/lib/strokes'

export type ArtworkSampleInput = {
  fills: FillOp[]
  strokes: Stroke[]
  x: number
  y: number
  /**
   * When true, include only garment artwork (fills + ink). Model/reference is
   * never sampled — eyedropper is for the designer's sketch materials.
   */
}

export type ArtworkSample = {
  hex: string
  /** True when an opaque artwork pixel was found at the point. */
  hit: boolean
}

/**
 * Sample the final composite pixel at a design-space point using the same
 * fill→ink layering as Konva preview / PNG / Magic capture (no reference).
 * Erasers punch both ink and fill pixels (per-fill chronology); croquis is never sampled.
 */
export function sampleArtworkPixel(input: ArtworkSampleInput): ArtworkSample {
  const px = Math.round(input.x)
  const py = Math.round(input.y)
  if (px < 0 || py < 0 || px >= DESIGN_WIDTH || py >= DESIGN_HEIGHT) {
    return { hex: '#000000', hit: false }
  }

  const canvas = document.createElement('canvas')
  canvas.width = DESIGN_WIDTH
  canvas.height = DESIGN_HEIGHT
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  if (!ctx) return { hex: '#000000', hit: false }

  ctx.clearRect(0, 0, DESIGN_WIDTH, DESIGN_HEIGHT)
  compositeFillAndInkLayers(ctx, {
    fills: input.fills,
    strokes: input.strokes,
    width: DESIGN_WIDTH,
    height: DESIGN_HEIGHT,
  })

  const data = ctx.getImageData(px, py, 1, 1).data
  const a = data[3]!
  if (a <= 20) return { hex: '#000000', hit: false }
  // Premultiply-safe: canvas pixels are already composited; convert to opaque hex.
  const r = data[0]!
  const g = data[1]!
  const b = data[2]!
  const hex = `#${[r, g, b].map((n) => n.toString(16).padStart(2, '0')).join('').toUpperCase()}`
  return { hex, hit: true }
}
