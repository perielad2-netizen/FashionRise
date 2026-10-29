/**
 * Extended drawing paper around the legacy croquis reference plane.
 *
 * Legacy design coordinates stay unchanged:
 *   x ∈ [0, DESIGN_WIDTH), y ∈ [0, DESIGN_HEIGHT)
 * Croquis / reference fit-contain still uses that rectangle.
 *
 * Extended paper (Issue #127):
 *   x ∈ [PAPER_ORIGIN_X, PAPER_ORIGIN_X + PAPER_WIDTH)
 *   y ∈ [PAPER_ORIGIN_Y, PAPER_ORIGIN_Y + PAPER_HEIGHT)
 * Strokes and fills may use negative or >legacy coordinates; mask rasterization
 * translates by −origin so canvas pixels stay non-negative.
 */
import { DESIGN_HEIGHT, DESIGN_WIDTH, type Stroke } from '@/lib/strokes'

/** Minimal fill geometry for bounds checks (avoids circular import with fills.ts). */
export type FillBoundsSource = {
  contour: number[]
  seedX: number
  seedY: number
}

/** Symmetric breathing room (design px) around the croquis reference. */
export const PAPER_MARGIN_X = 256
export const PAPER_MARGIN_Y = 256

/** Top-left of the drawable paper in design space (may be negative). */
export const PAPER_ORIGIN_X = -PAPER_MARGIN_X
export const PAPER_ORIGIN_Y = -PAPER_MARGIN_Y

/** Raster / paper size in design pixels (1280×1536). */
export const PAPER_WIDTH = DESIGN_WIDTH + 2 * PAPER_MARGIN_X
export const PAPER_HEIGHT = DESIGN_HEIGHT + 2 * PAPER_MARGIN_Y

export const PAPER_MASK_BYTES = PAPER_WIDTH * PAPER_HEIGHT

/**
 * Soft cap so a pathological region cannot paint the whole extended paper.
 * Raised vs the legacy 42% of 768×1024 so a closed oversized silhouette
 * (puffy dress / broad sleeves into the margins) can still fill — genuine
 * page-wide leaks still fail closed at the outer paper edge first.
 */
export const MAX_PAPER_FILL_PIXELS = Math.floor(PAPER_MASK_BYTES * 0.58)

export type PaperPoint = { x: number; y: number }

export function designToPaperX(x: number): number {
  return Math.round(x) - PAPER_ORIGIN_X
}

export function designToPaperY(y: number): number {
  return Math.round(y) - PAPER_ORIGIN_Y
}

export function paperToDesignX(ix: number): number {
  return ix + PAPER_ORIGIN_X
}

export function paperToDesignY(iy: number): number {
  return iy + PAPER_ORIGIN_Y
}

export function paperIndex(ix: number, iy: number): number {
  return iy * PAPER_WIDTH + ix
}

/** Design-space → linear paper-mask index, or -1 when outside the paper. */
export function designToPaperIndex(x: number, y: number): number {
  const ix = designToPaperX(x)
  const iy = designToPaperY(y)
  if (ix < 0 || iy < 0 || ix >= PAPER_WIDTH || iy >= PAPER_HEIGHT) return -1
  return paperIndex(ix, iy)
}

export function isInPaper(x: number, y: number): boolean {
  return designToPaperIndex(x, y) >= 0
}

export function isPaperEdgeIndex(ix: number, iy: number): boolean {
  return ix === 0 || iy === 0 || ix === PAPER_WIDTH - 1 || iy === PAPER_HEIGHT - 1
}

/** True when a design-space integer lies on the extended outer paper boundary. */
export function isOnPaperBoundary(x: number, y: number): boolean {
  const ix = designToPaperX(x)
  const iy = designToPaperY(y)
  if (ix < 0 || iy < 0 || ix >= PAPER_WIDTH || iy >= PAPER_HEIGHT) return false
  return isPaperEdgeIndex(ix, iy)
}

/**
 * Translate a Canvas2D context so design-space Path2D strokes paint onto a
 * PAPER_WIDTH×PAPER_HEIGHT raster (design 0,0 → pixel (−origin)).
 */
export function withPaperOrigin<T>(
  ctx: CanvasRenderingContext2D,
  paint: (ctx: CanvasRenderingContext2D) => T,
): T {
  ctx.save()
  ctx.translate(-PAPER_ORIGIN_X, -PAPER_ORIGIN_Y)
  try {
    return paint(ctx)
  } finally {
    ctx.restore()
  }
}

export function emptyPaperMask(): Uint8Array {
  return new Uint8Array(PAPER_MASK_BYTES)
}

export function clampPointToPaper(x: number, y: number): PaperPoint {
  const maxX = PAPER_ORIGIN_X + PAPER_WIDTH - 1e-3
  const maxY = PAPER_ORIGIN_Y + PAPER_HEIGHT - 1e-3
  return {
    x: Math.min(maxX, Math.max(PAPER_ORIGIN_X, x)),
    y: Math.min(maxY, Math.max(PAPER_ORIGIN_Y, y)),
  }
}

/** True when any stroke sample or fill contour vertex leaves the legacy croquis box. */
export function artworkExceedsLegacyBounds(
  strokes: Stroke[],
  fills: FillBoundsSource[] = [],
  pad = 0,
): boolean {
  const minX = -pad
  const minY = -pad
  const maxX = DESIGN_WIDTH + pad
  const maxY = DESIGN_HEIGHT + pad
  for (const stroke of strokes) {
    for (let i = 0; i + 1 < stroke.points.length; i += 3) {
      const x = stroke.points[i]!
      const y = stroke.points[i + 1]!
      if (!Number.isFinite(x) || !Number.isFinite(y)) continue
      if (x < minX || y < minY || x > maxX || y > maxY) return true
    }
  }
  for (const fill of fills) {
    const c = fill.contour
    for (let i = 0; i + 1 < c.length; i += 2) {
      const x = c[i]!
      const y = c[i + 1]!
      if (x < minX || y < minY || x > maxX || y > maxY) return true
    }
    if (
      fill.seedX < minX ||
      fill.seedY < minY ||
      fill.seedX > maxX ||
      fill.seedY > maxY
    ) {
      return true
    }
  }
  return false
}

/**
 * Export / capture frame: legacy 768×1024 when artwork stays inside the croquis
 * plane (pixel-identical reopen/export); full extended paper otherwise.
 */
export function resolveExportFrame(
  strokes: Stroke[],
  fills: FillBoundsSource[] = [],
): {
  mode: 'legacy' | 'paper'
  originX: number
  originY: number
  width: number
  height: number
} {
  if (!artworkExceedsLegacyBounds(strokes, fills)) {
    return {
      mode: 'legacy',
      originX: 0,
      originY: 0,
      width: DESIGN_WIDTH,
      height: DESIGN_HEIGHT,
    }
  }
  return {
    mode: 'paper',
    originX: PAPER_ORIGIN_X,
    originY: PAPER_ORIGIN_Y,
    width: PAPER_WIDTH,
    height: PAPER_HEIGHT,
  }
}
