/**
 * V2-0030 — rectangular selection eraser (structural ink edit).
 * Clips strokes/fills so only ink INSIDE the selection is removed; exterior remains.
 * Design/paper space throughout.
 */
import type { FillOp } from '@/lib/fills'
import { MAX_FILL_HOLES } from '@/lib/fills'
import { resolveLogicalLayer, type LogicalLayer } from '@/lib/professionalBrushes'
import { createStrokeId, type Stroke } from '@/lib/strokes'

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
   * Expand the erase AABB by half brush size when clipping strokes
   * (erase freehand is wider — 1.2× radius for erase strokes).
   */
  includeStrokeWidth?: boolean
  /** Ignore gestures smaller than this (design px) on either axis. */
  minSize?: number
}

const DEFAULT_MIN = 4
const EPS = 1e-6

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

export function expandPaperRect(rect: PaperRect, pad: number): PaperRect {
  if (pad <= 0) return rect
  return {
    x: rect.x - pad,
    y: rect.y - pad,
    width: rect.width + pad * 2,
    height: rect.height + pad * 2,
  }
}

export function intersectPaperRects(a: PaperRect, b: PaperRect): PaperRect | null {
  const x0 = Math.max(a.x, b.x)
  const y0 = Math.max(a.y, b.y)
  const x1 = Math.min(a.x + a.width, b.x + b.width)
  const y1 = Math.min(a.y + a.height, b.y + b.height)
  if (x1 - x0 < EPS || y1 - y0 < EPS) return null
  return { x: x0, y: y0, width: x1 - x0, height: y1 - y0 }
}

function pointInRect(x: number, y: number, rect: PaperRect, pad = 0): boolean {
  return (
    x >= rect.x - pad - EPS &&
    x <= rect.x + rect.width + pad + EPS &&
    y >= rect.y - pad - EPS &&
    y <= rect.y + rect.height + pad + EPS
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

function fillBounds(fill: FillOp): PaperRect | null {
  const c = fill.contour
  if (!Array.isArray(c) || c.length < 6) return null
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
  }
  if (!any) return null
  return { x: minX, y: minY, width: maxX - minX, height: maxY - minY }
}

/**
 * Segment ↔ AABB intersections as t in (0,1) along A→B.
 * Detects crossings even when both endpoints are outside the rectangle.
 */
export function segmentRectCrossingTs(
  ax: number,
  ay: number,
  bx: number,
  by: number,
  rect: PaperRect,
): number[] {
  const dx = bx - ax
  const dy = by - ay
  const edges: Array<{ x1: number; y1: number; x2: number; y2: number }> = [
    { x1: rect.x, y1: rect.y, x2: rect.x + rect.width, y2: rect.y },
    { x1: rect.x + rect.width, y1: rect.y, x2: rect.x + rect.width, y2: rect.y + rect.height },
    { x1: rect.x + rect.width, y1: rect.y + rect.height, x2: rect.x, y2: rect.y + rect.height },
    { x1: rect.x, y1: rect.y + rect.height, x2: rect.x, y2: rect.y },
  ]
  const ts: number[] = []
  for (const e of edges) {
    const ex = e.x2 - e.x1
    const ey = e.y2 - e.y1
    const den = dx * ey - dy * ex
    if (Math.abs(den) < EPS) continue
    const t = ((e.x1 - ax) * ey - (e.y1 - ay) * ex) / den
    const u = ((e.x1 - ax) * dy - (e.y1 - ay) * dx) / den
    if (t > EPS && t < 1 - EPS && u > -EPS && u < 1 + EPS) {
      ts.push(t)
    }
  }
  ts.sort((a, b) => a - b)
  // Dedupe near-identical crossings (corners).
  const out: number[] = []
  for (const t of ts) {
    if (out.length === 0 || Math.abs(out[out.length - 1]! - t) > 1e-5) out.push(t)
  }
  return out
}

export function segmentCrossesOrEntersRect(
  ax: number,
  ay: number,
  bx: number,
  by: number,
  rect: PaperRect,
): boolean {
  const aIn = pointInRect(ax, ay, rect)
  const bIn = pointInRect(bx, by, rect)
  if (aIn || bIn) return true
  return segmentRectCrossingTs(ax, ay, bx, by, rect).length > 0
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
  const eraseRect = expandPaperRect(rect, radius)
  const bounds = strokeBounds(stroke, 0)
  if (!bounds) return false
  if (!rectsIntersect(bounds, eraseRect)) return false
  const pts = stroke.points
  for (let i = 0; i + 1 < pts.length; i += 3) {
    const x = pts[i]!
    const y = pts[i + 1]!
    if (pointInRect(x, y, eraseRect)) return true
  }
  for (let i = 0; i + 4 < pts.length; i += 3) {
    if (
      segmentCrossesOrEntersRect(
        pts[i]!,
        pts[i + 1]!,
        pts[i + 3]!,
        pts[i + 4]!,
        eraseRect,
      )
    ) {
      return true
    }
  }
  return false
}

export function fillHitsRect(fill: FillOp, rect: PaperRect): boolean {
  const bounds = fillBounds(fill)
  if (!bounds) return false
  if (!rectsIntersect(bounds, rect)) return false
  const c = fill.contour
  for (let i = 0; i + 1 < c.length; i += 2) {
    if (pointInRect(c[i]!, c[i + 1]!, rect)) return true
  }
  // Contour edge crosses the erase rect (partial overlap without vertices inside).
  for (let i = 0; i + 3 < c.length; i += 2) {
    if (segmentCrossesOrEntersRect(c[i]!, c[i + 1]!, c[i + 2]!, c[i + 3]!, rect)) return true
  }
  // Close the loop.
  if (c.length >= 6) {
    const n = c.length
    if (segmentCrossesOrEntersRect(c[n - 2]!, c[n - 1]!, c[0]!, c[1]!, rect)) return true
  }
  // Selection fully inside fill AABB — treat as hit (hole punch).
  return (
    rect.x >= bounds.x - EPS &&
    rect.y >= bounds.y - EPS &&
    rect.x + rect.width <= bounds.x + bounds.width + EPS &&
    rect.y + rect.height <= bounds.y + bounds.height + EPS
  )
}

type Vertex = { x: number; y: number; pressure: number }

function lerpVertex(a: Vertex, b: Vertex, t: number): Vertex {
  return {
    x: a.x + (b.x - a.x) * t,
    y: a.y + (b.y - a.y) * t,
    pressure: a.pressure + (b.pressure - a.pressure) * t,
  }
}

function sameVertex(a: Vertex, b: Vertex): boolean {
  return Math.abs(a.x - b.x) < EPS && Math.abs(a.y - b.y) < EPS
}

/**
 * Keep polyline fragments that lie OUTSIDE `rect`.
 * Splits at boundary crossings so long strokes that traverse the selection survive outside.
 */
export function clipPolylineOutsideRect(
  points: number[],
  rect: PaperRect,
): number[][] {
  const verts: Vertex[] = []
  for (let i = 0; i + 1 < points.length; i += 3) {
    const x = points[i]!
    const y = points[i + 1]!
    const pressure = Number.isFinite(points[i + 2]) ? points[i + 2]! : 0.5
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue
    verts.push({ x, y, pressure })
  }
  if (verts.length === 0) return []
  if (verts.length === 1) {
    return pointInRect(verts[0]!.x, verts[0]!.y, rect) ? [] : [points.slice()]
  }

  const chains: Vertex[][] = []
  let current: Vertex[] = []

  const flush = () => {
    if (current.length >= 2) chains.push(current)
    current = []
  }

  const push = (v: Vertex) => {
    const last = current[current.length - 1]
    if (last && sameVertex(last, v)) return
    current.push(v)
  }

  for (let i = 0; i < verts.length - 1; i += 1) {
    const a = verts[i]!
    const b = verts[i + 1]!
    const ts = segmentRectCrossingTs(a.x, a.y, b.x, b.y, rect)
    const samples: Vertex[] = [a, ...ts.map((t) => lerpVertex(a, b, t)), b]

    for (let s = 0; s < samples.length - 1; s += 1) {
      const p0 = samples[s]!
      const p1 = samples[s + 1]!
      if (sameVertex(p0, p1)) continue
      const mx = (p0.x + p1.x) / 2
      const my = (p0.y + p1.y) / 2
      if (pointInRect(mx, my, rect)) {
        // Segment lies inside the erase rect — close any exterior chain at p0.
        if (current.length > 0) {
          push(p0)
          flush()
        }
        continue
      }
      // Exterior — continue or start a chain.
      if (current.length === 0) push(p0)
      push(p1)
    }
  }

  flush()

  return chains.map((chain) => {
    const out: number[] = []
    for (const v of chain) out.push(v.x, v.y, v.pressure)
    return out
  })
}

function cloneStrokeWithPoints(stroke: Stroke, points: number[]): Stroke {
  return {
    ...stroke,
    id: createStrokeId(),
    points,
  }
}

/**
 * Clip one stroke against the erase rect — keep exterior fragments only.
 */
export function clipStrokeOutsideRect(
  stroke: Stroke,
  rect: PaperRect,
  opts?: Pick<RectEraseOptions, 'includeStrokeWidth'>,
): Stroke[] {
  const includeWidth = opts?.includeStrokeWidth !== false
  const radius = includeWidth
    ? Math.max(0.5, (stroke.size || 1) * (stroke.tool === 'erase' ? 1.2 : 0.5))
    : 0
  const eraseRect = expandPaperRect(rect, radius)
  if (!strokeHitsRect(stroke, rect, opts)) return [stroke]
  const fragments = clipPolylineOutsideRect(stroke.points, eraseRect)
  return fragments
    .filter((pts) => pts.length >= 6)
    .map((pts) => cloneStrokeWithPoints(stroke, pts))
}

function rectToContour(rect: PaperRect): number[] {
  const x1 = rect.x + rect.width
  const y1 = rect.y + rect.height
  return [rect.x, rect.y, x1, rect.y, x1, y1, rect.x, y1]
}

/**
 * Punch the erase rectangle through a fill as an even-odd hole so exterior fill remains.
 * Fully covered fills are removed.
 */
export function clipFillOutsideRect(fill: FillOp, rect: PaperRect): FillOp | null {
  if (!fillHitsRect(fill, rect)) return fill
  const bounds = fillBounds(fill)
  if (!bounds) return fill
  // Selection covers the whole fill AABB → drop fill.
  if (
    rect.x <= bounds.x + EPS &&
    rect.y <= bounds.y + EPS &&
    rect.x + rect.width >= bounds.x + bounds.width - EPS &&
    rect.y + rect.height >= bounds.y + bounds.height - EPS
  ) {
    return null
  }
  const punched = intersectPaperRects(rect, expandPaperRect(bounds, 1))
  if (!punched || punched.width < 1 || punched.height < 1) return fill
  const hole = rectToContour(punched)
  const holes = [...(fill.holes ?? [])]
  if (holes.length >= MAX_FILL_HOLES) {
    // At hole capacity: still drop only if selection swallows most of the fill.
    const cover =
      (punched.width * punched.height) / Math.max(1, bounds.width * bounds.height)
    return cover >= 0.85 ? null : fill
  }
  holes.push(hole)
  return { ...fill, holes }
}

function strokeAffectedByLayer(stroke: Stroke, layer: LogicalLayer): boolean {
  if (stroke.tool === 'erase' && stroke.logicalLayer == null) {
    return layer === 'ink'
  }
  return resolveLogicalLayer(stroke) === layer
}

/**
 * Erase ink inside `rect` on the active logical layer — exterior artwork stays.
 * Shade/highlight rect-erase does not punch fills (matches freehand eraser rules).
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

  const strokes: Stroke[] = []
  let strokeChanged = false
  for (const s of artwork.strokes) {
    if (!strokeAffectedByLayer(s, layer) || !strokeHitsRect(s, rect, hitOpts)) {
      strokes.push(s)
      continue
    }
    const parts = clipStrokeOutsideRect(s, rect, hitOpts)
    if (parts.length !== 1 || parts[0] !== s) strokeChanged = true
    // parts empty → stroke fully erased inside selection
    if (parts.length === 0) strokeChanged = true
    strokes.push(...parts)
  }

  let fills = artwork.fills
  let fillChanged = false
  if (layer === 'ink') {
    const nextFills: FillOp[] = []
    for (const f of artwork.fills) {
      const clipped = clipFillOutsideRect(f, rect)
      if (clipped === null) {
        fillChanged = true
        continue
      }
      if (clipped !== f) fillChanged = true
      nextFills.push(clipped)
    }
    fills = nextFills
  }

  const changed = strokeChanged || fillChanged
  return { strokes, fills, changed }
}
