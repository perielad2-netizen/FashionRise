/**
 * V2-0030 — rectangular selection eraser (structural ink edit).
 * Operates in design/paper space. Does not invent paint-time destination-out strokes.
 */
import type { FillOp } from '@/lib/fills'
import { resolveLogicalLayer, type LogicalLayer } from '@/lib/professionalBrushes'
import type { Stroke } from '@/lib/strokes'

export type PaperRect = {
  x: number
  y: number
  width: number
  height: number
}

export type RectEraseOptions = {
  /** Active brush engine layer; default ink. */
  logicalLayer?: LogicalLayer
  /**
   * Expand stroke hit tests by half brush size (erase freehand is wider —
   * use stroke.size as-is for draw; 1.2× for erase strokes).
   */
  includeStrokeWidth?: boolean
  /** Ignore gestures smaller than this (design px) on either axis. */
  minSize?: number
}

const DEFAULT_MIN = 4

export function normalizePaperRect(
  a: { x: number; y: number },
  b: { x: number; y: number },
): PaperRect {
  const x = Math.min(a.x, b.x)
  const y = Math.min(a.y, b.y)
  return {
    x,
    y,
    width: Math.abs(b.x - a.x),
    height: Math.abs(b.y - a.y),
  }
}

export function isMeaningfulPaperRect(rect: PaperRect, minSize = DEFAULT_MIN): boolean {
  return rect.width >= minSize && rect.height >= minSize
}

export function rectsIntersect(a: PaperRect, b: PaperRect): boolean {
  return (
    a.x < b.x + b.width &&
    a.x + a.width > b.x &&
    a.y < b.y + b.height &&
    a.y + a.height > b.y
  )
}

function pointInRect(x: number, y: number, rect: PaperRect, pad = 0): boolean {
  return (
    x >= rect.x - pad &&
    x <= rect.x + rect.width + pad &&
    y >= rect.y - pad &&
    y <= rect.y + rect.height + pad
  )
}

/** Axis-aligned bounds of stroke polyline (+ optional radius pad). */
export function strokeBounds(stroke: Stroke, pad = 0): PaperRect | null {
  const pts = stroke.points
  if (pts.length < 2) return null
  let minX = Number.POSITIVE_INFINITY
  let minY = Number.POSITIVE_INFINITY
  let maxX = Number.NEGATIVE_INFINITY
  let maxY = Number.NEGATIVE_INFINITY
  for (let i = 0; i + 1 < pts.length; i += 3) {
    const x = pts[i]!
    const y = pts[i + 1]!
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue
    if (x < minX) minX = x
    if (y < minY) minY = y
    if (x > maxX) maxX = x
    if (y > maxY) maxY = y
  }
  if (!Number.isFinite(minX) || !Number.isFinite(minY)) return null
  return {
    x: minX - pad,
    y: minY - pad,
    width: maxX - minX + pad * 2,
    height: maxY - minY + pad * 2,
  }
}

export function strokeHitsRect(
  stroke: Stroke,
  rect: PaperRect,
  opts?: Pick<RectEraseOptions, 'includeStrokeWidth'>,
): boolean {
  const includeWidth = opts?.includeStrokeWidth !== false
  const radius = includeWidth
    ? Math.max(0.5, (stroke.size || 1) * (stroke.tool === 'erase' ? 1.2 : 0.5))
    : 0
  const bounds = strokeBounds(stroke, radius)
  if (!bounds) return false
  if (!rectsIntersect(bounds, rect)) return false
  // Point-in-rect (with pad) so long strokes that only skim the selection can hit.
  const pts = stroke.points
  for (let i = 0; i + 1 < pts.length; i += 3) {
    const x = pts[i]!
    const y = pts[i + 1]!
    if (pointInRect(x, y, rect, radius)) return true
  }
  return false
}

export function fillHitsRect(fill: FillOp, rect: PaperRect): boolean {
  const c = fill.contour
  if (!Array.isArray(c) || c.length < 6) return false
  let minX = Number.POSITIVE_INFINITY
  let minY = Number.POSITIVE_INFINITY
  let maxX = Number.NEGATIVE_INFINITY
  let maxY = Number.NEGATIVE_INFINITY
  let any = false
  for (let i = 0; i + 1 < c.length; i += 2) {
    const x = c[i]!
    const y = c[i + 1]!
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue
    any = true
    if (x < minX) minX = x
    if (y < minY) minY = y
    if (x > maxX) maxX = x
    if (y > maxY) maxY = y
    if (pointInRect(x, y, rect)) return true
  }
  if (!any) return false
  // Contour AABB intersects selection (covers large fills when only seed is outside).
  return rectsIntersect(
    { x: minX, y: minY, width: maxX - minX, height: maxY - minY },
    rect,
  )
}

function strokeAffectedByLayer(stroke: Stroke, layer: LogicalLayer): boolean {
  // Legacy erase (no logicalLayer) punches everything — treat as ink-target only.
  if (stroke.tool === 'erase' && stroke.logicalLayer == null) {
    return layer === 'ink'
  }
  return resolveLogicalLayer(stroke) === layer
}

/**
 * Remove strokes/fills that intersect `rect` on the active logical layer.
 * Shade/highlight rect-erase does not delete fills (matches stroke-eraser punch rules).
 */
export function eraseArtworkInRect(
  artwork: { strokes: Stroke[]; fills: FillOp[] },
  rect: PaperRect,
  opts?: RectEraseOptions,
): { strokes: Stroke[]; fills: FillOp[]; changed: boolean } {
  const minSize = opts?.minSize ?? DEFAULT_MIN
  if (!isMeaningfulPaperRect(rect, minSize)) {
    return { strokes: artwork.strokes, fills: artwork.fills, changed: false }
  }
  const layer: LogicalLayer = opts?.logicalLayer ?? 'ink'
  const hitOpts = { includeStrokeWidth: opts?.includeStrokeWidth !== false }

  const strokes = artwork.strokes.filter((s) => {
    if (!strokeAffectedByLayer(s, layer)) return true
    return !strokeHitsRect(s, rect, hitOpts)
  })

  const fills =
    layer === 'ink'
      ? artwork.fills.filter((f) => !fillHitsRect(f, rect))
      : artwork.fills

  const changed =
    strokes.length !== artwork.strokes.length || fills.length !== artwork.fills.length
  return { strokes, fills, changed }
}
