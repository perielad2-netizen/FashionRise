import { paintInkStrokes } from '@/lib/exportCanvas'
import { DESIGN_HEIGHT, DESIGN_WIDTH, type Stroke } from '@/lib/strokes'
import { createFillId, type FillOp, type FillStyle } from '@/lib/fills'

export type FloodFillOk = { ok: true; fill: FillOp }
export type FloodFillErr = {
  ok: false
  reason: 'open_outline' | 'empty_region' | 'outside' | 'too_large'
  message: string
}
export type FloodFillResult = FloodFillOk | FloodFillErr

/** Soft cap so a leak cannot paint the whole paper. */
export const MAX_FILL_PIXELS = Math.floor(DESIGN_WIDTH * DESIGN_HEIGHT * 0.42)

/**
 * Minimum positive interior (design pixels) accepted for a closed fill.
 * Was 24 — that rejected legitimate straps / tiny panels. Contour fallback
 * still requires a valid persistent polygon (≥3 points).
 */
export const MIN_FILL_PIXELS = 1

/** Default maximum ink dilation (px) considered when sealing freehand hairline gaps. */
export const DEFAULT_MAX_GAP_CLOSE = 2

/**
 * Flood-fill a closed ink region. Barriers are the **effective visible ink** after
 * draw/erase compositing (same destination-out rules as the canvas). Model
 * reference and fill contours are not barriers — garment parts are defined by
 * the ink the designer can still see.
 *
 * Adaptive gap closing: try visible-ink barriers first (preserves narrow necks /
 * straps), then progressively dilate only when the undilated flood escapes. The
 * first safely closed candidate wins — dilation never overrides a valid
 * undilated enclosure.
 */
export function floodFillRegion(input: {
  strokes: Stroke[]
  x: number
  y: number
  style: FillStyle
  /**
   * Maximum barrier dilation (px) to try when sealing freehand gaps.
   * `0` = visible ink only. Default `2`.
   */
  gapClose?: number
}): FloodFillResult {
  const maxGap = Math.max(0, Math.min(4, Math.floor(input.gapClose ?? DEFAULT_MAX_GAP_CLOSE)))
  const raw = buildInkBarrierMask(input.strokes, 0)
  return floodFillAdaptive({
    rawBarrier: raw,
    x: input.x,
    y: input.y,
    style: input.style,
    maxGap,
  })
}

/**
 * Adaptive multi-pass fill against a raw (undilated) barrier mask.
 * Exported for deterministic synthetic-barrier tests without Canvas 2D.
 */
export function floodFillAdaptive(input: {
  rawBarrier: Uint8Array
  x: number
  y: number
  style: FillStyle
  maxGap?: number
}): FloodFillResult {
  const maxGap = Math.max(0, Math.min(4, Math.floor(input.maxGap ?? DEFAULT_MAX_GAP_CLOSE)))
  const sx = Math.round(input.x)
  const sy = Math.round(input.y)
  if (sx < 0 || sy < 0 || sx >= DESIGN_WIDTH || sy >= DESIGN_HEIGHT) {
    return { ok: false, reason: 'outside', message: 'Tap inside a closed garment outline to fill.' }
  }

  const raw = input.rawBarrier
  const seedIdx = sy * DESIGN_WIDTH + sx
  if (raw[seedIdx]) {
    return {
      ok: false,
      reason: 'outside',
      message: 'Tap inside a closed shape, not on the outline.',
    }
  }

  let lastOpen: FloodFillErr | null = null
  let lastEmpty: FloodFillErr | null = null
  let sealedSeed = false

  for (let gap = 0; gap <= maxGap; gap += 1) {
    const barrier = gap === 0 ? raw : dilateMask(raw, gap)
    if (barrier[seedIdx]) {
      // Dilation invented a wall under the click (narrow channel). Stronger
      // dilation only makes this worse — stop and report a useful error.
      sealedSeed = true
      break
    }

    const result = floodFillAgainstBarrier({
      barrier,
      x: input.x,
      y: input.y,
      style: input.style,
    })

    if (result.ok) {
      // Prefer the least dilation that yields a closed interior.
      return result
    }
    if (result.reason === 'open_outline' || result.reason === 'too_large') {
      lastOpen = result
      continue
    }
    if (result.reason === 'empty_region') {
      lastEmpty = result
      continue
    }
    // outside on a dilated barrier should be rare (we checked seedIdx).
    if (result.reason === 'outside') {
      sealedSeed = true
      break
    }
  }

  if (sealedSeed && lastOpen) {
    return lastOpen
  }
  if (sealedSeed) {
    return {
      ok: false,
      reason: 'empty_region',
      message:
        'That spot is too narrow to fill from here. Tap inside a slightly wider part of the closed shape.',
    }
  }
  if (lastOpen) return lastOpen
  if (lastEmpty) return lastEmpty
  return {
    ok: false,
    reason: 'open_outline',
    message: 'Outline looks open — close the shape so the fill stays inside the dress.',
  }
}

/** Core flood-fill against a prebuilt barrier mask (testable without Canvas 2D). */
export function floodFillAgainstBarrier(input: {
  barrier: Uint8Array
  x: number
  y: number
  style: FillStyle
  /** Override minimum interior pixels (default {@link MIN_FILL_PIXELS}). */
  minPixels?: number
  /** Override contour RDP tolerance; omit for size-adaptive tolerance. */
  simplifyTolerance?: number
}): FloodFillResult {
  const sx = Math.round(input.x)
  const sy = Math.round(input.y)
  if (sx < 0 || sy < 0 || sx >= DESIGN_WIDTH || sy >= DESIGN_HEIGHT) {
    return { ok: false, reason: 'outside', message: 'Tap inside a closed garment outline to fill.' }
  }

  const barrier = input.barrier
  const idx = sy * DESIGN_WIDTH + sx
  if (barrier[idx]) {
    return {
      ok: false,
      reason: 'outside',
      message: 'Tap inside a closed shape, not on the outline.',
    }
  }

  const visited = new Uint8Array(DESIGN_WIDTH * DESIGN_HEIGHT)
  const stackX = new Int32Array(DESIGN_WIDTH * DESIGN_HEIGHT)
  const stackY = new Int32Array(DESIGN_WIDTH * DESIGN_HEIGHT)
  let sp = 0
  stackX[sp] = sx
  stackY[sp] = sy
  sp += 1
  visited[idx] = 1

  let count = 0
  let minX = sx
  let minY = sy
  let maxX = sx
  let maxY = sy

  while (sp > 0) {
    sp -= 1
    const cx = stackX[sp]!
    const cy = stackY[sp]!
    count += 1
    if (cx === 0 || cy === 0 || cx === DESIGN_WIDTH - 1 || cy === DESIGN_HEIGHT - 1) {
      // Fail closed as soon as the flood escapes to the paper edge — do not keep
      // expanding until MAX_FILL_PIXELS (which would mis-report open outlines).
      return {
        ok: false,
        reason: 'open_outline',
        message: 'Outline looks open — close the shape so the fill stays inside the dress.',
      }
    }
    if (count > MAX_FILL_PIXELS) {
      return {
        ok: false,
        reason: 'too_large',
        message: 'That area is too open to fill safely. Close the outline and try again.',
      }
    }
    if (cx < minX) minX = cx
    if (cy < minY) minY = cy
    if (cx > maxX) maxX = cx
    if (cy > maxY) maxY = cy

    push(cx + 1, cy)
    push(cx - 1, cy)
    push(cx, cy + 1)
    push(cx, cy - 1)
  }

  function push(nx: number, ny: number) {
    if (nx < 0 || ny < 0 || nx >= DESIGN_WIDTH || ny >= DESIGN_HEIGHT) return
    const i = ny * DESIGN_WIDTH + nx
    if (visited[i] || barrier[i]) return
    visited[i] = 1
    stackX[sp] = nx
    stackY[sp] = ny
    sp += 1
  }

  const minPixels = Math.max(1, Math.floor(input.minPixels ?? MIN_FILL_PIXELS))
  if (count < minPixels) {
    return {
      ok: false,
      reason: 'empty_region',
      message: 'No fillable interior there. Tap inside a closed outline (not on the ink).',
    }
  }

  let contour = traceContour(visited, minX, minY, maxX, maxY)
  if (contour.length < 6) {
    // Degenerate Moore walk on micro-regions (1–few pixels): emit the pixel bbox
    // so a genuinely closed positive area remains persistable.
    contour = [minX, minY, maxX + 1, minY, maxX + 1, maxY + 1, minX, maxY + 1]
  }

  const tolerance =
    input.simplifyTolerance ??
    contourSimplifyTolerance(count, maxX - minX + 1, maxY - minY + 1)

  return {
    ok: true,
    fill: {
      id: createFillId(),
      contour: simplifyContour(contour, tolerance),
      style: input.style,
      seedX: input.x,
      seedY: input.y,
    },
  }
}

/**
 * Rasterize draw+erase strokes into a barrier mask matching what the user sees.
 * Exported for regression tests (erased seams must not remain invisible barriers).
 */
export function buildInkBarrierMask(strokes: Stroke[], gapClose = 0): Uint8Array {
  const canvas = document.createElement('canvas')
  canvas.width = DESIGN_WIDTH
  canvas.height = DESIGN_HEIGHT
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  if (!ctx) return new Uint8Array(DESIGN_WIDTH * DESIGN_HEIGHT)

  ctx.clearRect(0, 0, DESIGN_WIDTH, DESIGN_HEIGHT)
  // Same ink compositing as Konva/PNG: erase uses destination-out on ink only.
  paintInkStrokes(ctx, strokes)

  const img = ctx.getImageData(0, 0, DESIGN_WIDTH, DESIGN_HEIGHT)
  const raw = new Uint8Array(DESIGN_WIDTH * DESIGN_HEIGHT)
  for (let i = 0, p = 0; i < raw.length; i += 1, p += 4) {
    raw[i] = img.data[p + 3]! > 12 ? 1 : 0
  }
  // Morphological dilate closes freehand hairline gaps at corners while staying
  // derived from rendered ink (not inventing invisible seams).
  if (gapClose <= 0) return raw
  return dilateMask(raw, gapClose)
}

/** Square morphological dilate — exported for narrow-channel regression fixtures. */
export function dilateMask(mask: Uint8Array, radius: number): Uint8Array {
  if (radius <= 0) return mask
  const out = new Uint8Array(mask.length)
  for (let y = 0; y < DESIGN_HEIGHT; y += 1) {
    for (let x = 0; x < DESIGN_WIDTH; x += 1) {
      if (!mask[y * DESIGN_WIDTH + x]) continue
      const y0 = Math.max(0, y - radius)
      const y1 = Math.min(DESIGN_HEIGHT - 1, y + radius)
      const x0 = Math.max(0, x - radius)
      const x1 = Math.min(DESIGN_WIDTH - 1, x + radius)
      for (let ny = y0; ny <= y1; ny += 1) {
        for (let nx = x0; nx <= x1; nx += 1) {
          out[ny * DESIGN_WIDTH + nx] = 1
        }
      }
    }
  }
  return out
}

/** Lower RDP tolerance for small / narrow regions so thin necks survive. */
export function contourSimplifyTolerance(
  pixelCount: number,
  bboxWidth: number,
  bboxHeight: number,
): number {
  const minDim = Math.min(bboxWidth, bboxHeight)
  if (pixelCount < 48 || minDim <= 6) return 0.35
  if (minDim <= 12 || pixelCount < 220) return 0.75
  return 1.4
}

/** Moore-neighbour boundary walk → flat [x,y,...] contour. */
function traceContour(
  mask: Uint8Array,
  minX: number,
  minY: number,
  maxX: number,
  maxY: number,
): number[] {
  let startX = -1
  let startY = -1
  outer: for (let y = minY; y <= maxY; y += 1) {
    for (let x = minX; x <= maxX; x += 1) {
      if (!mask[y * DESIGN_WIDTH + x]) continue
      // left neighbour empty → boundary start
      if (x === 0 || !mask[y * DESIGN_WIDTH + (x - 1)]) {
        startX = x
        startY = y
        break outer
      }
    }
  }
  if (startX < 0) return []

  const dx = [1, 1, 0, -1, -1, -1, 0, 1]
  const dy = [0, 1, 1, 1, 0, -1, -1, -1]
  const points: number[] = []
  let x = startX
  let y = startY
  let dir = 0
  const maxSteps = DESIGN_WIDTH * DESIGN_HEIGHT

  for (let step = 0; step < maxSteps; step += 1) {
    points.push(x, y)
    let found = false
    for (let k = 0; k < 8; k += 1) {
      const nd = (dir + 6 + k) % 8 // prefer turning left
      const nx = x + dx[nd]!
      const ny = y + dy[nd]!
      if (nx < 0 || ny < 0 || nx >= DESIGN_WIDTH || ny >= DESIGN_HEIGHT) continue
      if (!mask[ny * DESIGN_WIDTH + nx]) continue
      x = nx
      y = ny
      dir = nd
      found = true
      break
    }
    if (!found) break
    if (x === startX && y === startY && points.length > 4) break
  }
  return points
}

function simplifyContour(contour: number[], tolerance: number): number[] {
  if (contour.length <= 8 || tolerance <= 0) return contour
  const pts: { x: number; y: number }[] = []
  for (let i = 0; i < contour.length; i += 2) {
    pts.push({ x: contour[i]!, y: contour[i + 1]! })
  }
  const keep = rdp(pts, tolerance)
  const out: number[] = []
  for (const p of keep) out.push(Math.round(p.x), Math.round(p.y))
  if (out.length >= 6) return out
  return contour
}

function rdp(points: { x: number; y: number }[], epsilon: number): { x: number; y: number }[] {
  if (points.length < 3) return points
  let maxDist = 0
  let index = 0
  const first = points[0]!
  const last = points[points.length - 1]!
  for (let i = 1; i < points.length - 1; i += 1) {
    const d = perpDist(points[i]!, first, last)
    if (d > maxDist) {
      maxDist = d
      index = i
    }
  }
  if (maxDist > epsilon) {
    const left = rdp(points.slice(0, index + 1), epsilon)
    const right = rdp(points.slice(index), epsilon)
    return left.slice(0, -1).concat(right)
  }
  return [first, last]
}

function perpDist(
  p: { x: number; y: number },
  a: { x: number; y: number },
  b: { x: number; y: number },
): number {
  const dx = b.x - a.x
  const dy = b.y - a.y
  if (dx === 0 && dy === 0) return Math.hypot(p.x - a.x, p.y - a.y)
  const t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / (dx * dx + dy * dy)
  const x = a.x + t * dx
  const y = a.y + t * dy
  return Math.hypot(p.x - x, p.y - y)
}
