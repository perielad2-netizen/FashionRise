import { compositeFillAndInkLayers } from '@/lib/exportCanvas'
import type { FillOp } from '@/lib/fills'
import {
  PAPER_HEIGHT,
  PAPER_ORIGIN_X,
  PAPER_ORIGIN_Y,
  PAPER_WIDTH,
  designToPaperIndex,
  isInPaper,
} from '@/lib/paperBounds'
import type { Stroke } from '@/lib/strokes'

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
 * Supports the extended paper (negative / >legacy design coordinates).
 */
export function sampleArtworkPixel(input: ArtworkSampleInput): ArtworkSample {
  const px = Math.round(input.x)
  const py = Math.round(input.y)
  if (!isInPaper(px, py)) {
    return { hex: '#000000', hit: false }
  }

  const canvas = document.createElement('canvas')
  canvas.width = PAPER_WIDTH
  canvas.height = PAPER_HEIGHT
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  if (!ctx) return { hex: '#000000', hit: false }

  ctx.clearRect(0, 0, PAPER_WIDTH, PAPER_HEIGHT)
  compositeFillAndInkLayers(ctx, {
    fills: input.fills,
    strokes: input.strokes,
    width: PAPER_WIDTH,
    height: PAPER_HEIGHT,
    originX: PAPER_ORIGIN_X,
    originY: PAPER_ORIGIN_Y,
  })

  const idx = designToPaperIndex(px, py)
  if (idx < 0) return { hex: '#000000', hit: false }
  const ix = idx % PAPER_WIDTH
  const iy = Math.floor(idx / PAPER_WIDTH)
  const data = ctx.getImageData(ix, iy, 1, 1).data
  const a = data[3]!
  if (a <= 20) return { hex: '#000000', hit: false }
  // Premultiply-safe: canvas pixels are already composited; convert to opaque hex.
  const r = data[0]!
  const g = data[1]!
  const b = data[2]!
  const hex = `#${[r, g, b].map((n) => n.toString(16).padStart(2, '0')).join('').toUpperCase()}`
  return { hex, hit: true }
}
