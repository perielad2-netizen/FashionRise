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
 * Compact gate clusters at or below this size are treated as accidental seam
 * punch-throughs (prefer the dilated panel-local fill). Elongated corridors
 * (hourglass necks) are kept as intentional connections.
 *
 * Remaining limitation: intentional corridors shorter than ~3px along their
 * long axis may be treated conservatively as punch-throughs (prefer panel
 * isolation over silent merge). Perfect automatic intent recognition is not claimed.
 */
const ACCIDENTAL_GATE_MAX_DIM = 3
const ACCIDENTAL_GATE_MAX_PIXELS = 8

type FloodExploreOk = {
  ok: true
  visited: Uint8Array
  count: number
  minX: number
  minY: number
  maxX: number
  maxY: number
}
type FloodExploreResult = FloodExploreOk | FloodFillErr

/**
 * Flood-fill a closed ink region. Barriers are the **effective visible ink** after
 * draw/erase compositing (same destination-out rules as the canvas). Model
 * reference and fill contours are not barriers — garment parts are defined by
 * the ink the designer can still see.
 *
 * Adaptive gap closing:
 * 1. Prefer undilated visible ink (preserves narrow necks / straps).
 * 2. If undilated succeeds but a modest dilation reveals that the region only
 *    connected through a *compact* punch-through in an internal seam, prefer the
 *    dilated (panel-local) result — without globally dilating first.
 * 3. If undilated escapes to the paper edge, escalate gap-close to seal hairline
 *    perimeter gaps.
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

  const undilated = exploreFlood(raw, sx, sy)
  if (undilated.ok) {
    // Check whether a modest dilation would isolate a panel by sealing only a
    // compact internal punch-through (not an elongated intentional neck).
    let chosen: FloodExploreOk = undilated
    for (let gap = 1; gap <= maxGap; gap += 1) {
      const dilated = dilateMask(raw, gap)
      if (dilated[seedIdx]) break
      const panel = exploreFlood(dilated, sx, sy)
      if (!panel.ok) continue
      if (isAccidentalPunchThrough(raw, dilated, undilated, panel)) {
        chosen = panel
        // Keep the least dilation that seals the punch-through.
        break
      }
    }
    return finalizeFlood(chosen, input.x, input.y, input.style)
  }

  // Undilated escaped / too large / empty — escalate gap-close for perimeter hairlines.
  let lastOpen: FloodFillErr | null =
    undilated.ok === false &&
    (undilated.reason === 'open_outline' || undilated.reason === 'too_large')
      ? undilated
      : null
  let lastEmpty: FloodFillErr | null =
    undilated.ok === false && undilated.reason === 'empty_region' ? undilated : null
  let sealedSeed = false

  for (let gap = 1; gap <= maxGap; gap += 1) {
    const barrier = dilateMask(raw, gap)
    if (barrier[seedIdx]) {
      sealedSeed = true
      break
    }
    const explored = exploreFlood(barrier, sx, sy)
    if (explored.ok) {
      return finalizeFlood(explored, input.x, input.y, input.style)
    }
    if (explored.reason === 'open_outline' || explored.reason === 'too_large') {
      lastOpen = explored
      continue
    }
    if (explored.reason === 'empty_region') {
      lastEmpty = explored
      continue
    }
    if (explored.reason === 'outside') {
      sealedSeed = true
      break
    }
  }

  if (sealedSeed && lastOpen) return lastOpen
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
  const idx = sy * DESIGN_WIDTH + sx
  if (input.barrier[idx]) {
    return {
      ok: false,
      reason: 'outside',
      message: 'Tap inside a closed shape, not on the outline.',
    }
  }
  const explored = exploreFlood(input.barrier, sx, sy, input.minPixels)
  if (!explored.ok) return explored
  return finalizeFlood(explored, input.x, input.y, input.style, input.simplifyTolerance)
}

/**
 * Explore a closed flood region. Exported for seam-safety / pixel-level tests.
 * Allocations are bounded by DESIGN_WIDTH*DESIGN_HEIGHT; exploration stops at
 * paper-edge escape or {@link MAX_FILL_PIXELS}.
 */
export function exploreFlood(
  barrier: Uint8Array,
  sx: number,
  sy: number,
  minPixels: number = MIN_FILL_PIXELS,
): FloodExploreResult {
  if (sx < 0 || sy < 0 || sx >= DESIGN_WIDTH || sy >= DESIGN_HEIGHT) {
    return { ok: false, reason: 'outside', message: 'Tap inside a closed garment outline to fill.' }
  }
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

  const minPx = Math.max(1, Math.floor(minPixels))
  if (count < minPx) {
    return {
      ok: false,
      reason: 'empty_region',
      message: 'No fillable interior there. Tap inside a closed outline (not on the ink).',
    }
  }

  return { ok: true, visited, count, minX, minY, maxX, maxY }
}

/**
 * True when dilation seals only a *compact* bridge between the undilated region
 * and a smaller panel-local region — typical of a 1–2px hole in an internal seam.
 *
 * Method: under dilation the seed stays in `panel` while a large `leaked` area
 * (still open, still in the undilated flood) becomes unreachable. A BFS through
 * the undilated mask finds a shortest path from panel → leaked; bridge pixels on
 * that path are those sealed by dilation (`dilated && !raw`). Compact bridges
 * (seam punch-throughs) return true → prefer panel-local fill. Elongated bridges
 * (hourglass necks) return false → keep the connected undilated fill.
 *
 * Limitation: intentional corridors shorter than ~3px along their long axis can
 * look like punch-throughs; we prefer panel isolation over silent merge. Perfect
 * automatic intent recognition is not claimed.
 */
export function isAccidentalPunchThrough(
  rawBarrier: Uint8Array,
  dilatedBarrier: Uint8Array,
  undilated: FloodExploreOk,
  panel: FloodExploreOk,
): boolean {
  if (panel.count >= undilated.count) return false

  // Leaked = still open under dilation, reached undilated, but not in panel.
  let leakedCount = 0
  let leakSeed = -1
  const x0 = Math.max(0, Math.min(undilated.minX, panel.minX) - 2)
  const x1 = Math.min(DESIGN_WIDTH - 1, Math.max(undilated.maxX, panel.maxX) + 2)
  const y0 = Math.max(0, Math.min(undilated.minY, panel.minY) - 2)
  const y1 = Math.min(DESIGN_HEIGHT - 1, Math.max(undilated.maxY, panel.maxY) + 2)

  for (let y = y0; y <= y1; y += 1) {
    for (let x = x0; x <= x1; x += 1) {
      const i = y * DESIGN_WIDTH + x
      if (!undilated.visited[i] || panel.visited[i] || dilatedBarrier[i]) continue
      leakedCount += 1
      if (leakSeed < 0) leakSeed = i
    }
  }

  // Require a real second enclosure — not a few fringe pixels eaten by dilate.
  if (leakSeed < 0 || leakedCount < 24) return false
  if (leakedCount < Math.min(48, Math.floor(panel.count * 0.15))) return false

  // BFS from the panel through undilated.visited to the nearest leaked pixel.
  const parent = new Int32Array(DESIGN_WIDTH * DESIGN_HEIGHT)
  parent.fill(-1)
  const qx = new Int32Array(undilated.count + 8)
  const qy = new Int32Array(undilated.count + 8)
  let qh = 0
  let qt = 0
  const seen = new Uint8Array(DESIGN_WIDTH * DESIGN_HEIGHT)

  for (let y = panel.minY; y <= panel.maxY; y += 1) {
    for (let x = panel.minX; x <= panel.maxX; x += 1) {
      const i = y * DESIGN_WIDTH + x
      if (!panel.visited[i]) continue
      seen[i] = 1
      qx[qt] = x
      qy[qt] = y
      qt += 1
    }
  }

  let meet = -1
  while (qh < qt && meet < 0) {
    const cx = qx[qh]!
    const cy = qy[qh]!
    qh += 1
    for (const [dx, dy] of [
      [1, 0],
      [-1, 0],
      [0, 1],
      [0, -1],
    ] as const) {
      const nx = cx + dx
      const ny = cy + dy
      if (nx < 0 || ny < 0 || nx >= DESIGN_WIDTH || ny >= DESIGN_HEIGHT) continue
      const ni = ny * DESIGN_WIDTH + nx
      if (seen[ni] || !undilated.visited[ni]) continue
      seen[ni] = 1
      parent[ni] = cy * DESIGN_WIDTH + cx
      if (!panel.visited[ni] && !dilatedBarrier[ni]) {
        meet = ni
        break
      }
      qx[qt] = nx
      qy[qt] = ny
      qt += 1
    }
  }
  if (meet < 0) return false

  // Walk back; bridge = path pixels sealed by dilation (not original ink).
  let bridgeCount = 0
  let bMinX = DESIGN_WIDTH
  let bMinY = DESIGN_HEIGHT
  let bMaxX = 0
  let bMaxY = 0
  let cur = meet
  let guard = 0
  const maxPath = undilated.count + 8
  while (cur >= 0 && guard < maxPath) {
    guard += 1
    if (panel.visited[cur]) break
    if (dilatedBarrier[cur] && !rawBarrier[cur]) {
      const bx = cur % DESIGN_WIDTH
      const by = (cur / DESIGN_WIDTH) | 0
      bridgeCount += 1
      if (bx < bMinX) bMinX = bx
      if (by < bMinY) bMinY = by
      if (bx > bMaxX) bMaxX = bx
      if (by > bMaxY) bMaxY = by
    }
    cur = parent[cur]!
  }

  if (bridgeCount === 0) return false
  const w = bMaxX - bMinX + 1
  const h = bMaxY - bMinY + 1
  const minDim = Math.min(w, h)
  const maxDim = Math.max(w, h)

  // Elongated corridor (hourglass neck / strap passage): keep connected fill.
  // Require a meaningful length so a 3×1 morphological seam cut (wall thicken
  // + 1px hole) is NOT treated as a neck.
  if (maxDim >= 6 && maxDim >= 3 * minDim) return false
  if (bridgeCount > 16 && maxDim >= 6) return false

  // Compact punch-through (1–2px seam hole, short diagonal join, eraser nick).
  // Morphological dilate-1 around a vertical seam makes a ~3×1 bridge bbox.
  if (bridgeCount <= 16 && maxDim <= 5) return true
  return false
}

function finalizeFlood(
  explored: FloodExploreOk,
  seedX: number,
  seedY: number,
  style: FillStyle,
  simplifyTolerance?: number,
): FloodFillResult {
  const { visited, count, minX, minY, maxX, maxY } = explored
  let contour = traceContour(visited, minX, minY, maxX, maxY)
  if (contour.length < 6) {
    contour = [minX, minY, maxX + 1, minY, maxX + 1, maxY + 1, minX, maxY + 1]
  }

  const minSpan = minScanlineSpan(visited, minX, minY, maxX, maxY)
  const tolerance =
    simplifyTolerance ??
    contourSimplifyTolerance(count, maxX - minX + 1, maxY - minY + 1, minSpan)

  const simplified = simplifyContour(contour, tolerance)
  return {
    ok: true,
    fill: {
      id: createFillId(),
      contour: simplified,
      style,
      seedX,
      seedY,
    },
  }
}

/** Narrowest contiguous horizontal/vertical run inside the filled region. */
export function minScanlineSpan(
  visited: Uint8Array,
  minX: number,
  minY: number,
  maxX: number,
  maxY: number,
): number {
  let minSpan = Infinity
  for (let y = minY; y <= maxY; y += 1) {
    let run = 0
    for (let x = minX; x <= maxX; x += 1) {
      if (visited[y * DESIGN_WIDTH + x]) {
        run += 1
      } else if (run > 0) {
        if (run < minSpan) minSpan = run
        run = 0
      }
    }
    if (run > 0 && run < minSpan) minSpan = run
  }
  for (let x = minX; x <= maxX; x += 1) {
    let run = 0
    for (let y = minY; y <= maxY; y += 1) {
      if (visited[y * DESIGN_WIDTH + x]) {
        run += 1
      } else if (run > 0) {
        if (run < minSpan) minSpan = run
        run = 0
      }
    }
    if (run > 0 && run < minSpan) minSpan = run
  }
  return Number.isFinite(minSpan) ? minSpan : Math.min(maxX - minX + 1, maxY - minY + 1)
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

/**
 * Lower RDP tolerance for small / narrow regions so thin necks survive.
 * `minInteriorSpan` is the narrowest scanline run (neck width) when known —
 * used even when the overall bbox is large (hourglass with fat lobes).
 */
export function contourSimplifyTolerance(
  pixelCount: number,
  bboxWidth: number,
  bboxHeight: number,
  minInteriorSpan?: number,
): number {
  const minDim = Math.min(bboxWidth, bboxHeight)
  const span = minInteriorSpan ?? minDim
  // Thin corridor anywhere — keep every vertex (no RDP) so the neck stays
  // a positive-area passage after edge-based contour tracing.
  if (span <= 2) return 0
  if (span <= 4 || pixelCount < 48 || minDim <= 6) return 0.35
  if (minDim <= 12 || pixelCount < 220) return 0.75
  return 1.4
}

/** Even-odd point-in-polygon for flat [x,y,...] contours (test / validation helper). */
export function pointInContour(contour: number[], x: number, y: number): boolean {
  let inside = false
  for (let i = 0, j = contour.length - 2; i < contour.length; i += 2) {
    const xi = contour[i]!
    const yi = contour[i + 1]!
    const xj = contour[j]!
    const yj = contour[j + 1]!
    const intersect =
      yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi + Number.EPSILON) + xi
    if (intersect) inside = !inside
    j = i
  }
  return inside
}

/**
 * True when the unit square for design pixel (px, py) is covered by the contour.
 * Contours are edge-based half-open squares, so sample the pixel centre.
 */
export function contourCoversPixel(contour: number[], px: number, py: number): boolean {
  return pointInContour(contour, px + 0.5, py + 0.5)
}

/**
 * Edge-based outer contour of filled pixels as unit squares [x,x+1]×[y,y+1].
 * Gives 1px necks / straps positive polygon area (Moore pixel-centre walks
 * collapse a 1px corridor to a zero-width polyline that canvas won't paint).
 */
function traceContour(
  mask: Uint8Array,
  minX: number,
  minY: number,
  maxX: number,
  maxY: number,
): number[] {
  // Directed edge key: pack (x,y,dir) where dir 0=E,1=S,2=W,3=N along grid lines.
  // Grid nodes span [minX, maxX+1] × [minY, maxY+1].
  const nodeW = maxX - minX + 2
  const nodeH = maxY - minY + 2
  if (nodeW <= 1 || nodeH <= 1) return []

  const edgeSet = new Set<number>()
  const pack = (x: number, y: number, dir: number) =>
    (((y - minY) * nodeW + (x - minX)) << 2) | dir

  const filled = (x: number, y: number) => {
    if (x < minX || y < minY || x > maxX || y > maxY) return false
    return !!mask[y * DESIGN_WIDTH + x]
  }

  for (let y = minY; y <= maxY; y += 1) {
    for (let x = minX; x <= maxX; x += 1) {
      if (!mask[y * DESIGN_WIDTH + x]) continue
      // Top edge → east, bottom → west, left → north, right → south (CCW).
      if (!filled(x, y - 1)) edgeSet.add(pack(x, y, 0))
      if (!filled(x, y + 1)) edgeSet.add(pack(x + 1, y + 1, 2))
      if (!filled(x - 1, y)) edgeSet.add(pack(x, y + 1, 3))
      if (!filled(x + 1, y)) edgeSet.add(pack(x + 1, y, 1))
    }
  }
  if (edgeSet.size === 0) return []

  // Start at topmost-leftmost east edge.
  let startKey = -1
  let bestY = Infinity
  let bestX = Infinity
  for (const key of edgeSet) {
    const dir = key & 3
    if (dir !== 0) continue
    const node = key >> 2
    const x = (node % nodeW) + minX
    const y = ((node / nodeW) | 0) + minY
    if (y < bestY || (y === bestY && x < bestX)) {
      bestY = y
      bestX = x
      startKey = key
    }
  }
  if (startKey < 0) {
    startKey = edgeSet.values().next().value as number
  }

  const points: number[] = []
  let key = startKey
  const maxSteps = edgeSet.size + 4
  for (let step = 0; step < maxSteps; step += 1) {
    if (!edgeSet.has(key)) break
    edgeSet.delete(key)
    const dir = key & 3
    const node = key >> 2
    const x = (node % nodeW) + minX
    const y = ((node / nodeW) | 0) + minY
    points.push(x, y)

    const ex = x + (dir === 0 ? 1 : dir === 2 ? -1 : 0)
    const ey = y + (dir === 1 ? 1 : dir === 3 ? -1 : 0)

    // Prefer left turn, then straight, then right (outer boundary CCW).
    const order = [(dir + 3) & 3, dir, (dir + 1) & 3, (dir + 2) & 3]
    let next = -1
    for (const nd of order) {
      const nk = pack(ex, ey, nd)
      if (edgeSet.has(nk)) {
        next = nk
        break
      }
    }
    if (next < 0) break
    key = next
    if (key === startKey) break
  }

  if (points.length >= 6) return points
  // Degenerate fallback: axis-aligned bbox of the filled region (half-open).
  return [minX, minY, maxX + 1, minY, maxX + 1, maxY + 1, minX, maxY + 1]
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
