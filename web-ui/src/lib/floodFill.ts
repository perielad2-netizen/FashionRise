import { paintInkStrokes } from '@/lib/exportCanvas'
import { strokeToSvgPath } from '@/lib/freehand'
import { DESIGN_HEIGHT, DESIGN_WIDTH, type Stroke } from '@/lib/strokes'
import { createFillId, type FillOp, type FillStyle } from '@/lib/fills'

export type FloodFillOk = { ok: true; fill: FillOp }
export type FloodFillErr = {
  ok: false
  reason: 'open_outline' | 'empty_region' | 'outside' | 'too_large' | 'unsupported_cutout'
  message: string
  /** Approximate leak / gap location in design space when detectable. */
  gapHint?: { x: number; y: number }
  /** True when a bounded Close-small-gaps seal would likely close this outline. */
  suggestCloseGaps?: boolean
}
export type FloodFillResult = FloodFillOk | FloodFillErr

/** Soft cap so a leak cannot paint the whole paper. */
export const MAX_FILL_PIXELS = Math.floor(DESIGN_WIDTH * DESIGN_HEIGHT * 0.42)

/** Default morphological dilate (design px) after sealed-tip rasterization. */
export const DEFAULT_GAP_CLOSE_PX = 2
/**
 * Automatic cross-stroke endpoint seal (design px). Kept tight so intentional
 * slits / adjacent panels within ~4–5px are not silently bridged. sealTips +
 * morphological dilate handle tapered tip leaks on visually connected ink.
 */
export const DEFAULT_ENDPOINT_SEAL_PX = 2.5
/** Explicit "Close small gaps" seal radius (still bounded; will not span armholes). */
export const STRONG_ENDPOINT_SEAL_PX = 12
/** Same-stroke start≈end self-close allowance under automatic fill. */
export const DEFAULT_SELF_CLOSE_PX = 3.5
/** Minimum mutual facing alignment (dot product) to treat endpoints as same-contour. */
export const MIN_ENDPOINT_FACING = 0.45

/**
 * Flood-fill a closed ink region. Barriers are the **effective visible ink** after
 * draw/erase compositing (same destination-out rules as the canvas), painted with
 * seal-tip freehand paths so tapered joins that look closed do not leak. Model
 * reference and fill contours are not barriers.
 */
export function floodFillRegion(input: {
  strokes: Stroke[]
  x: number
  y: number
  style: FillStyle
  /** Dilate ink barriers by this many pixels to close tiny gaps. */
  gapClose?: number
  /**
   * When true, apply a stronger but still bounded endpoint seal (Close small gaps).
   * Does not silently bridge large intentional openings.
   */
  closeSmallGaps?: boolean
}): FloodFillResult {
  const endpointSeal = input.closeSmallGaps ? STRONG_ENDPOINT_SEAL_PX : DEFAULT_ENDPOINT_SEAL_PX
  const gapClose = input.gapClose ?? DEFAULT_GAP_CLOSE_PX
  const layers = buildInkBarrierLayers(input.strokes, gapClose, { endpointSealPx: endpointSeal })
  const barrier = layers.barrier
  const result = floodFillAgainstBarrier({
    barrier,
    visibleInk: layers.visibleInk,
    x: input.x,
    y: input.y,
    style: input.style,
  })
  if (result.ok || result.reason !== 'open_outline' || input.closeSmallGaps) {
    return result
  }

  // Diagnose whether a bounded stronger seal would help — do not apply it silently.
  const strongLayers = buildInkBarrierLayers(input.strokes, Math.max(gapClose, 3), {
    endpointSealPx: STRONG_ENDPOINT_SEAL_PX,
  })
  const probe = floodFillAgainstBarrier({
    barrier: strongLayers.barrier,
    visibleInk: strongLayers.visibleInk,
    x: input.x,
    y: input.y,
    style: input.style,
  })
  if (probe.ok) {
    const hint = locateGapHint(barrier, input.x, input.y)
    return {
      ok: false,
      reason: 'open_outline',
      message:
        'Outline has a small gap. Use Close small gaps, then tap Fill again — or close the join with the pencil.',
      ...(hint ? { gapHint: hint } : {}),
      suggestCloseGaps: true,
    }
  }

  const hint = locateGapHint(barrier, input.x, input.y)
  return {
    ...result,
    ...(hint ? { gapHint: hint } : { gapHint: undefined }),
    suggestCloseGaps: false,
    message: hint
      ? 'Outline looks open near the highlighted spot — close it so the fill stays inside the shape.'
      : 'Outline looks open — close the shape so the fill stays inside.',
  }
}

/** Core flood-fill against a prebuilt barrier mask (testable without Canvas 2D). */
export function floodFillAgainstBarrier(input: {
  barrier: Uint8Array
  /**
   * Pre-dilation visible ink (post seal). Used so cutout safety still sees hollows
   * that morphological dilate sealed into the barrier. Defaults to `barrier`.
   */
  visibleInk?: Uint8Array
  x: number
  y: number
  style: FillStyle
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
      // Do not advertise the paper edge as a gap location — locateGapHint decides.
      return {
        ok: false,
        reason: 'open_outline',
        message: 'Outline looks open — close the shape so the fill stays inside.',
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

  if (count < 24) {
    return {
      ok: false,
      reason: 'empty_region',
      message: 'No closed garment region found there. Draw a closed outline first.',
    }
  }

  const contour = traceContour(visited, minX, minY, maxX, maxY)
  if (contour.length < 6) {
    return {
      ok: false,
      reason: 'empty_region',
      message: 'Could not build a fill shape. Try tapping nearer the centre of the region.',
    }
  }

  // Persist the same contour the canvas will paint — cutout safety must judge this
  // polygon, not a pre-simplify trace the user never sees.
  const simplified = simplifyContour(contour, 1.4)

  // Single-contour FillOp cannot represent holes. Use pre-dilation visible ink so
  // a hollow sealed only by morphological expand still fails closed — without
  // treating the dilate fringe along the flood frontier as a cutout.
  const visibleInk = input.visibleInk ?? barrier
  if (floodEnclosesUnsupportedCutout(visited, barrier, visibleInk, simplified)) {
    return {
      ok: false,
      reason: 'unsupported_cutout',
      message:
        'This area has an inner cutout. Fills can’t keep holes empty yet — tap a simpler closed area, or erase the inner outline first.',
    }
  }

  return {
    ok: true,
    fill: {
      id: createFillId(),
      contour: simplified,
      style: input.style,
      seedX: input.x,
      seedY: input.y,
    },
  }
}

export type BarrierMaskOptions = {
  /** Max distance (design px) to bridge stroke endpoints / self-close tips. */
  endpointSealPx?: number
}

export type InkBarrierLayers = {
  /** Post seal-tip + endpoint seal, before morphological dilate (visible drawing). */
  visibleInk: Uint8Array
  /** Final flood barrier (visibleInk after optional dilate). */
  barrier: Uint8Array
}

/**
 * Rasterize draw+erase strokes into visible-ink + dilated barrier layers.
 * Exported for regression tests (erased seams must not remain invisible barriers).
 */
export function buildInkBarrierLayers(
  strokes: Stroke[],
  gapClose = DEFAULT_GAP_CLOSE_PX,
  options?: BarrierMaskOptions,
): InkBarrierLayers {
  const empty = new Uint8Array(DESIGN_WIDTH * DESIGN_HEIGHT)
  const canvas = document.createElement('canvas')
  canvas.width = DESIGN_WIDTH
  canvas.height = DESIGN_HEIGHT
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  if (!ctx) return { visibleInk: empty, barrier: empty }

  ctx.clearRect(0, 0, DESIGN_WIDTH, DESIGN_HEIGHT)
  // Seal-tip paths for draw ink so tapered pencil tips do not open joins in the mask.
  paintInkStrokes(ctx, strokes, { sealTips: true })

  const img = ctx.getImageData(0, 0, DESIGN_WIDTH, DESIGN_HEIGHT)
  const raw = new Uint8Array(DESIGN_WIDTH * DESIGN_HEIGHT)
  for (let i = 0, p = 0; i < raw.length; i += 1, p += 4) {
    raw[i] = img.data[p + 3]! > 12 ? 1 : 0
  }

  const eraseCoverage = buildEraseCoverageMask(strokes)
  const sealPx = options?.endpointSealPx ?? DEFAULT_ENDPOINT_SEAL_PX
  if (sealPx > 0) {
    sealStrokeJoints(raw, strokes, sealPx, { eraseCoverage })
  }

  // Morphological dilate closes freehand hairline gaps at corners while staying
  // derived from rendered ink (not inventing invisible seams across panels).
  // Never grow into erased openings unless later pencil ink already restored them.
  if (gapClose <= 0) return { visibleInk: raw, barrier: raw }
  return { visibleInk: raw, barrier: dilateMask(raw, gapClose, { eraseCoverage }) }
}

/**
 * Rasterize draw+erase strokes into a barrier mask matching what the user sees,
 * with seal-tip freehand paths plus a bounded, eraser-aware endpoint joint seal.
 */
export function buildInkBarrierMask(
  strokes: Stroke[],
  gapClose = DEFAULT_GAP_CLOSE_PX,
  options?: BarrierMaskOptions,
): Uint8Array {
  return buildInkBarrierLayers(strokes, gapClose, options).barrier
}

export type StrokeEndpoint = {
  x: number
  y: number
  size: number
  strokeId: string
  which: 'start' | 'end'
  /** Unit tangent pointing out of the stroke tip into open space. */
  tx: number
  ty: number
}

/** Collect first/last design-space points of draw strokes (stride-3 freehand). */
export function collectDrawStrokeEndpoints(strokes: Stroke[]): StrokeEndpoint[] {
  const out: StrokeEndpoint[] = []
  for (const stroke of strokes) {
    if (stroke.tool !== 'draw') continue
    const pts: { x: number; y: number }[] = []
    for (let i = 0; i + 1 < stroke.points.length; i += 3) {
      const x = stroke.points[i]
      const y = stroke.points[i + 1]
      if (x === undefined || y === undefined) continue
      if (!Number.isFinite(x) || !Number.isFinite(y)) continue
      pts.push({ x, y })
    }
    if (pts.length === 0) continue
    const first = pts[0]!
    const last = pts[pts.length - 1]!
    const startTan = tipTangent(pts, 'start')
    out.push({
      x: first.x,
      y: first.y,
      size: stroke.size,
      strokeId: stroke.id,
      which: 'start',
      tx: startTan.tx,
      ty: startTan.ty,
    })
    if (pts.length > 1) {
      const endTan = tipTangent(pts, 'end')
      out.push({
        x: last.x,
        y: last.y,
        size: stroke.size,
        strokeId: stroke.id,
        which: 'end',
        tx: endTan.tx,
        ty: endTan.ty,
      })
    }
  }
  return out
}

function tipTangent(
  pts: { x: number; y: number }[],
  which: 'start' | 'end',
): { tx: number; ty: number } {
  if (pts.length < 2) return { tx: 0, ty: 0 }
  const a = which === 'start' ? pts[1]! : pts[pts.length - 2]!
  const b = which === 'start' ? pts[0]! : pts[pts.length - 1]!
  const dx = b.x - a.x
  const dy = b.y - a.y
  const len = Math.hypot(dx, dy)
  if (len < 1e-6) return { tx: 0, ty: 0 }
  return { tx: dx / len, ty: dy / len }
}

/** Rasterize erase strokes alone — sealed pixels under this mask must not return. */
export function buildEraseCoverageMask(strokes: Stroke[]): Uint8Array {
  const eraseOnly = strokes.filter((s) => s.tool === 'erase')
  const empty = new Uint8Array(DESIGN_WIDTH * DESIGN_HEIGHT)
  if (eraseOnly.length === 0) return empty
  const canvas = document.createElement('canvas')
  canvas.width = DESIGN_WIDTH
  canvas.height = DESIGN_HEIGHT
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  if (!ctx) return empty
  const Path2DCtor = typeof Path2D === 'undefined' ? null : Path2D
  if (!Path2DCtor) return empty
  ctx.clearRect(0, 0, DESIGN_WIDTH, DESIGN_HEIGHT)
  // Paint erase silhouettes as solid source-over (same Path2D as destination-out erase).
  for (const stroke of eraseOnly) {
    const svg = strokeToSvgPath(stroke)
    if (!svg) continue
    ctx.fillStyle = '#000000'
    ctx.fill(new Path2DCtor(svg))
  }
  const img = ctx.getImageData(0, 0, DESIGN_WIDTH, DESIGN_HEIGHT)
  const mask = new Uint8Array(DESIGN_WIDTH * DESIGN_HEIGHT)
  for (let i = 0, p = 0; i < mask.length; i += 1, p += 4) {
    mask[i] = img.data[p + 3]! > 12 ? 1 : 0
  }
  return mask
}

export type SealJointsOptions = {
  /** Pixels cleared by erase strokes — seals must not resurrect them. */
  eraseCoverage?: Uint8Array
  /** Override facing threshold (tests). */
  minFacing?: number
  /** Allow larger same-stroke self-close than cross-stroke maxGapPx. */
  selfClosePx?: number
}

function tipHasAliveInk(mask: Uint8Array, x: number, y: number, radius: number): boolean {
  const r = Math.max(1, Math.ceil(radius))
  const x0 = Math.max(0, Math.round(x) - r)
  const x1 = Math.min(DESIGN_WIDTH - 1, Math.round(x) + r)
  const y0 = Math.max(0, Math.round(y) - r)
  const y1 = Math.min(DESIGN_HEIGHT - 1, Math.round(y) + r)
  for (let py = y0; py <= y1; py += 1) {
    for (let px = x0; px <= x1; px += 1) {
      if (mask[py * DESIGN_WIDTH + px]) return true
    }
  }
  return false
}

function endpointsFaceEachOther(a: StrokeEndpoint, b: StrokeEndpoint, minFacing: number): boolean {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const dist = Math.hypot(dx, dy)
  if (dist < 1e-6) return true
  const ux = dx / dist
  const uy = dy / dist
  // Each tip's outbound tangent should point roughly toward the other tip.
  const aFace = a.tx * ux + a.ty * uy
  const bFace = b.tx * -ux + b.ty * -uy
  return aFace >= minFacing && bFace >= minFacing
}

/**
 * Bridge nearby same-contour stroke endpoints into the barrier mask only.
 * - Requires mutual facing tangents (rejects parallel adjacent panels).
 * - Never stamps over erase coverage (preserves deliberate openings).
 * - Uses a spatial hash so hundreds of strokes stay responsive.
 */
export function sealStrokeJoints(
  mask: Uint8Array,
  strokes: Stroke[],
  maxGapPx: number,
  options?: SealJointsOptions,
): void {
  if (maxGapPx <= 0) return
  const eraseCoverage = options?.eraseCoverage
  const minFacing = options?.minFacing ?? MIN_ENDPOINT_FACING
  const selfClosePx = options?.selfClosePx ?? Math.max(maxGapPx, DEFAULT_SELF_CLOSE_PX)
  const ends = collectDrawStrokeEndpoints(strokes)
  if (ends.length === 0) return

  const trySeal = (a: StrokeEndpoint, b: StrokeEndpoint, maxDist: number, requireFacing: boolean) => {
    const d = Math.hypot(a.x - b.x, a.y - b.y)
    if (d <= 0.5 || d > maxDist) return
    if (requireFacing && !endpointsFaceEachOther(a, b, minFacing)) return
    const tipR = Math.max(2, Math.ceil(Math.max(a.size, b.size)))
    // Both tips must still show alive ink — erased junctions fail this check.
    if (!tipHasAliveInk(mask, a.x, a.y, tipR) || !tipHasAliveInk(mask, b.x, b.y, tipR)) return
    if (eraseCoverage && capsuleHitsErase(eraseCoverage, a.x, a.y, b.x, b.y)) return
    const r = Math.max(2, Math.ceil((a.size + b.size) / 4) + 1)
    stampCapsule(mask, a.x, a.y, b.x, b.y, r, eraseCoverage)
  }

  // Self-close nearly finished single strokes (start≈end).
  const byStroke = new Map<string, StrokeEndpoint[]>()
  for (const e of ends) {
    const list = byStroke.get(e.strokeId) ?? []
    list.push(e)
    byStroke.set(e.strokeId, list)
  }
  for (const list of byStroke.values()) {
    const start = list.find((e) => e.which === 'start')
    const end = list.find((e) => e.which === 'end')
    if (!start || !end) continue
    trySeal(start, end, selfClosePx, false)
  }

  // Cross-stroke joins — spatial hash O(n · buckets) instead of O(n²).
  const cell = Math.max(4, Math.ceil(maxGapPx))
  const grid = new Map<string, number[]>()
  for (let i = 0; i < ends.length; i += 1) {
    const e = ends[i]!
    const key = `${Math.floor(e.x / cell)}:${Math.floor(e.y / cell)}`
    const bucket = grid.get(key)
    if (bucket) bucket.push(i)
    else grid.set(key, [i])
  }
  const neighborOffsets = [-1, 0, 1]
  for (let i = 0; i < ends.length; i += 1) {
    const a = ends[i]!
    const gx = Math.floor(a.x / cell)
    const gy = Math.floor(a.y / cell)
    for (const ox of neighborOffsets) {
      for (const oy of neighborOffsets) {
        const bucket = grid.get(`${gx + ox}:${gy + oy}`)
        if (!bucket) continue
        for (const j of bucket) {
          if (j <= i) continue
          const b = ends[j]!
          if (a.strokeId === b.strokeId) continue
          trySeal(a, b, maxGapPx, true)
        }
      }
    }
  }
}

function capsuleHitsErase(
  eraseCoverage: Uint8Array,
  x0: number,
  y0: number,
  x1: number,
  y1: number,
): boolean {
  const steps = Math.max(1, Math.ceil(Math.hypot(x1 - x0, y1 - y0)))
  let hits = 0
  let samples = 0
  for (let s = 0; s <= steps; s += 1) {
    const t = s / steps
    const x = Math.round(x0 + (x1 - x0) * t)
    const y = Math.round(y0 + (y1 - y0) * t)
    if (x < 0 || y < 0 || x >= DESIGN_WIDTH || y >= DESIGN_HEIGHT) continue
    samples += 1
    if (eraseCoverage[y * DESIGN_WIDTH + x]) hits += 1
  }
  // Any substantial erase along the prospective bridge vetoes the seal.
  return samples > 0 && hits / samples >= 0.25
}

function stampCapsule(
  mask: Uint8Array,
  x0: number,
  y0: number,
  x1: number,
  y1: number,
  radius: number,
  eraseCoverage?: Uint8Array,
): void {
  const steps = Math.max(1, Math.ceil(Math.hypot(x1 - x0, y1 - y0)))
  for (let s = 0; s <= steps; s += 1) {
    const t = s / steps
    stampDisk(mask, x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, radius, eraseCoverage)
  }
}

function stampDisk(
  mask: Uint8Array,
  cx: number,
  cy: number,
  radius: number,
  eraseCoverage?: Uint8Array,
): void {
  const r = Math.max(1, Math.round(radius))
  const xMid = Math.round(cx)
  const yMid = Math.round(cy)
  const r2 = r * r
  for (let y = yMid - r; y <= yMid + r; y += 1) {
    if (y < 0 || y >= DESIGN_HEIGHT) continue
    for (let x = xMid - r; x <= xMid + r; x += 1) {
      if (x < 0 || x >= DESIGN_WIDTH) continue
      const dx = x - xMid
      const dy = y - yMid
      if (dx * dx + dy * dy > r2) continue
      const i = y * DESIGN_WIDTH + x
      // Never restore ink a designer deliberately erased.
      if (eraseCoverage && eraseCoverage[i]) continue
      mask[i] = 1
    }
  }
}

export type DilateMaskOptions = {
  /**
   * Pixels cleared by erase strokes. Dilation must not recreate a deliberate
   * opening. Later pencil ink already present in `mask` is kept (chronology).
   */
  eraseCoverage?: Uint8Array
}

export function dilateMask(
  mask: Uint8Array,
  radius: number,
  options?: DilateMaskOptions,
): Uint8Array {
  if (radius <= 0) return mask
  const eraseCoverage = options?.eraseCoverage
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
          const i = ny * DESIGN_WIDTH + nx
          // Do not grow into erased openings unless redrawn ink already lives there.
          if (eraseCoverage && eraseCoverage[i] && !mask[i]) continue
          out[i] = 1
        }
      }
    }
  }
  return out
}

/**
 * Locate a supported gap mouth for UI highlighting.
 *
 * Returns a flooded empty cell that is adjacent to barrier ink and lies on the
 * shortest path from the seed toward the paper-edge escape — never the paper
 * edge itself. Returns null when evidence is insufficient (caller must use
 * neutral wording without "near highlighted spot").
 */
export function locateGapHint(
  barrier: Uint8Array,
  seedX: number,
  seedY: number,
): { x: number; y: number } | null {
  const sx = Math.round(seedX)
  const sy = Math.round(seedY)
  if (sx < 0 || sy < 0 || sx >= DESIGN_WIDTH || sy >= DESIGN_HEIGHT) return null
  if (barrier[sy * DESIGN_WIDTH + sx]) return null

  const visited = new Uint8Array(DESIGN_WIDTH * DESIGN_HEIGHT)
  const parent = new Int32Array(DESIGN_WIDTH * DESIGN_HEIGHT)
  parent.fill(-1)
  const qx = new Int32Array(DESIGN_WIDTH * DESIGN_HEIGHT)
  const qy = new Int32Array(DESIGN_WIDTH * DESIGN_HEIGHT)
  let head = 0
  let tail = 0
  qx[tail] = sx
  qy[tail] = sy
  tail += 1
  visited[sy * DESIGN_WIDTH + sx] = 1
  let edgeX = -1
  let edgeY = -1
  let steps = 0
  const limit = Math.min(MAX_FILL_PIXELS, DESIGN_WIDTH * DESIGN_HEIGHT)

  while (head < tail && steps < limit) {
    const cx = qx[head]!
    const cy = qy[head]!
    head += 1
    steps += 1
    if (cx === 0 || cy === 0 || cx === DESIGN_WIDTH - 1 || cy === DESIGN_HEIGHT - 1) {
      edgeX = cx
      edgeY = cy
      break
    }
    const neighbors = [
      [cx + 1, cy],
      [cx - 1, cy],
      [cx, cy + 1],
      [cx, cy - 1],
    ] as const
    for (const [nx, ny] of neighbors) {
      if (nx < 0 || ny < 0 || nx >= DESIGN_WIDTH || ny >= DESIGN_HEIGHT) continue
      const i = ny * DESIGN_WIDTH + nx
      if (visited[i] || barrier[i]) continue
      visited[i] = 1
      parent[i] = cy * DESIGN_WIDTH + cx
      qx[tail] = nx
      qy[tail] = ny
      tail += 1
    }
  }
  if (edgeX < 0) return null

  // Walk parent chain from the edge escape back toward the seed. The *first*
  // flooded cell near barrier ink (and not on the paper edge) is the gap mouth
  // nearest the escape — do not overwrite with later corridor cells. A small
  // Chebyshev radius catches narrow mouths when the path runs through the gap
  // centre; wide openings that never graze ink stay suppressed (null).
  let i = edgeY * DESIGN_WIDTH + edgeX
  const edgeGuard = 2
  const mouthRadius = 2
  while (i >= 0) {
    const x = i % DESIGN_WIDTH
    const y = Math.floor(i / DESIGN_WIDTH)
    const onPaperEdge =
      x <= edgeGuard ||
      y <= edgeGuard ||
      x >= DESIGN_WIDTH - 1 - edgeGuard ||
      y >= DESIGN_HEIGHT - 1 - edgeGuard
    if (!onPaperEdge && cellNearBarrier(barrier, x, y, mouthRadius)) {
      return { x, y }
    }
    i = parent[i]!
  }
  // Ambiguous / insufficient evidence — suppress marker (neutral message).
  return null
}

function cellNearBarrier(barrier: Uint8Array, x: number, y: number, radius: number): boolean {
  for (let dy = -radius; dy <= radius; dy += 1) {
    for (let dx = -radius; dx <= radius; dx += 1) {
      const nx = x + dx
      const ny = y + dy
      if (nx < 0 || ny < 0 || nx >= DESIGN_WIDTH || ny >= DESIGN_HEIGHT) continue
      if (barrier[ny * DESIGN_WIDTH + nx]) return true
    }
  }
  return false
}

/**
 * Minimum painted∖flooded empty visible-ink pixels that prove a real cutout.
 * Allows a few discrete fringe mismatches from contour simplification without
 * missing a closed 4–8px design-pixel opening (~12–50 cells).
 */
const MIN_UNSUPPORTED_CUTOUT_PIXELS = 4

/**
 * True when painting the persisted fill contour would cover an inner cutout the
 * flood never visited.
 *
 * Compares against **pre-dilation visible ink** so morphological expand cannot
 * hide a hollow that is empty in the rendered sketch. Dilate-only fringe along
 * the flood frontier (barrier ∧ ¬visibleInk ∧ adjacent to visited) is ignored —
 * that is contour/simplify mismatch, not a cutout.
 */
function floodEnclosesUnsupportedCutout(
  visited: Uint8Array,
  barrier: Uint8Array,
  visibleInk: Uint8Array,
  contour: number[],
): boolean {
  const coverage = rasterizeContourCoverage(contour)
  if (!coverage) return false
  const { mask, minX, minY, maxX, maxY } = coverage
  let holePixels = 0
  for (let y = minY; y <= maxY; y += 1) {
    const row = y * DESIGN_WIDTH
    for (let x = minX; x <= maxX; x += 1) {
      const i = row + x
      if (!mask[i]) continue
      if (visited[i]) continue
      // Skip actual drawn ink; empty sketch cells may still be cutouts.
      if (visibleInk[i]) continue
      // Surviving hollow (empty even after dilate) — classic cutout.
      if (!barrier[i]) {
        holePixels += 1
        if (holePixels >= MIN_UNSUPPORTED_CUTOUT_PIXELS) return true
        continue
      }
      // Dilate sealed this cell. Count only interior sealed hollows, not the
      // 1px dilate fringe hugging the flood frontier from contour simplify.
      if (!cellNearVisited(visited, x, y, 1)) {
        holePixels += 1
        if (holePixels >= MIN_UNSUPPORTED_CUTOUT_PIXELS) return true
      }
    }
  }
  return false
}

function cellNearVisited(visited: Uint8Array, x: number, y: number, radius: number): boolean {
  const y0 = Math.max(0, y - radius)
  const y1 = Math.min(DESIGN_HEIGHT - 1, y + radius)
  const x0 = Math.max(0, x - radius)
  const x1 = Math.min(DESIGN_WIDTH - 1, x + radius)
  for (let ny = y0; ny <= y1; ny += 1) {
    const row = ny * DESIGN_WIDTH
    for (let nx = x0; nx <= x1; nx += 1) {
      if (visited[row + nx]) return true
    }
  }
  return false
}

/**
 * Integer scanline fill of a closed contour (pixel centres). Matches even-odd
 * geometry without canvas antialiasing so small cutouts cannot hide between samples.
 */
function rasterizeContourCoverage(
  contour: number[],
): { mask: Uint8Array; minX: number; minY: number; maxX: number; maxY: number } | null {
  const n = Math.floor(contour.length / 2)
  if (n < 3) return null
  let minX = DESIGN_WIDTH - 1
  let minY = DESIGN_HEIGHT - 1
  let maxX = 0
  let maxY = 0
  for (let i = 0; i < n; i += 1) {
    const x = contour[i * 2]!
    const y = contour[i * 2 + 1]!
    if (x < minX) minX = Math.floor(x)
    if (y < minY) minY = Math.floor(y)
    if (x > maxX) maxX = Math.ceil(x)
    if (y > maxY) maxY = Math.ceil(y)
  }
  minX = Math.max(0, minX - 1)
  minY = Math.max(0, minY - 1)
  maxX = Math.min(DESIGN_WIDTH - 1, maxX + 1)
  maxY = Math.min(DESIGN_HEIGHT - 1, maxY + 1)

  const mask = new Uint8Array(DESIGN_WIDTH * DESIGN_HEIGHT)
  for (let y = minY; y <= maxY; y += 1) {
    const ys = y + 0.5
    const crossings: number[] = []
    for (let i = 0, j = n - 1; i < n; j = i, i += 1) {
      const yi = contour[i * 2 + 1]!
      const yj = contour[j * 2 + 1]!
      if (yi > ys === yj > ys) continue
      const xi = contour[i * 2]!
      const xj = contour[j * 2]!
      const t = (ys - yi) / (yj - yi)
      crossings.push(xi + t * (xj - xi))
    }
    if (crossings.length < 2) continue
    crossings.sort((a, b) => a - b)
    for (let k = 0; k + 1 < crossings.length; k += 2) {
      const xStart = Math.max(minX, Math.ceil(crossings[k]! - 1e-9))
      const xEnd = Math.min(maxX, Math.floor(crossings[k + 1]! - 1e-9))
      const row = y * DESIGN_WIDTH
      for (let x = xStart; x <= xEnd; x += 1) {
        mask[row + x] = 1
      }
    }
  }
  return { mask, minX, minY, maxX, maxY }
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
  if (contour.length <= 8) return contour
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
