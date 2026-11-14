/**
 * Professional Sketch Engine V1 — brush kinds, logical layers, Canvas2D paint.
 * Deterministic charcoal (seeded). Tapered ink stays perfect-freehand SVG.
 */

import { strokeToSvgPath } from '@/lib/freehand'
import type { FillOp } from '@/lib/fills'
import { paintFillOps } from '@/lib/paintFills'
import type { Stroke } from '@/lib/strokes'

export type BrushKind = 'tapered' | 'charcoal' | 'airbrush'

export type LogicalLayer = 'ink' | 'shade' | 'highlight'

export type StrokeBlendMode = 'source-over' | 'multiply' | 'soft-light' | 'screen'

export const BRUSH_KINDS: readonly BrushKind[] = ['tapered', 'charcoal', 'airbrush'] as const
export const LOGICAL_LAYERS: readonly LogicalLayer[] = ['ink', 'shade', 'highlight'] as const
export const STROKE_BLEND_MODES: readonly StrokeBlendMode[] = [
  'source-over',
  'multiply',
  'soft-light',
  'screen',
] as const

export const DEFAULT_BRUSH_KIND: BrushKind = 'tapered'
export const DEFAULT_LOGICAL_LAYER: LogicalLayer = 'ink'
export const DEFAULT_BLEND_MODE: StrokeBlendMode = 'source-over'
export const DEFAULT_FLOW = 0.45
export const DEFAULT_SOFTNESS = 0.65
export const DEFAULT_TEXTURE_INTENSITY = 0.7

/** Charcoal stamp renderer (PR #185 early). Kept for saved-stroke compatibility. */
export const CHARCOAL_RENDERER_V1 = 1
/** Continuous soft ribbon — Charcoal Shading V2. */
export const CHARCOAL_RENDERER_V2 = 2
/**
 * Pencil-tip charcoal — hard tip/core with soft vanish away from the tip
 * (radial + along-stroke lift). Kept for strokes saved as renderer 3.
 */
export const CHARCOAL_RENDERER_V3 = 3
/**
 * Width-gradient charcoal — solid along the stroke, hard on one edge,
 * soft vanish across the width (angled charcoal / side-of-pencil mark).
 */
export const CHARCOAL_RENDERER_V4 = 4
export const CHARCOAL_RENDERER_CURRENT = CHARCOAL_RENDERER_V4

/** Per-kind default sizes (design-space px). Ink stays fine; charcoal/airbrush shade wider. */
export const BRUSH_KIND_DEFAULT_SIZE_PX: Record<BrushKind, number> = {
  tapered: 1.75,
  charcoal: 18,
  airbrush: 22,
}

export type BrushEngineState = {
  brushKind: BrushKind
  logicalLayer: LogicalLayer
  blendMode: StrokeBlendMode
  flow: number
  softness: number
  textureIntensity: number
  /** When true, shade/highlight soft-clip to garment fill alpha if available. */
  garmentMask: boolean
}

export const DEFAULT_BRUSH_ENGINE: BrushEngineState = {
  brushKind: DEFAULT_BRUSH_KIND,
  logicalLayer: DEFAULT_LOGICAL_LAYER,
  blendMode: DEFAULT_BLEND_MODE,
  flow: DEFAULT_FLOW,
  softness: DEFAULT_SOFTNESS,
  textureIntensity: DEFAULT_TEXTURE_INTENSITY,
  garmentMask: false,
}

/** Suggested engine defaults when switching brush kind (size handled separately). */
export function defaultsForBrushKind(kind: BrushKind): Partial<BrushEngineState> {
  if (kind === 'tapered') {
    return {
      brushKind: 'tapered',
      logicalLayer: 'ink',
      blendMode: 'source-over',
      flow: 1,
      softness: 0.2,
      textureIntensity: 0,
      garmentMask: false,
    }
  }
  if (kind === 'charcoal') {
    return {
      brushKind: 'charcoal',
      logicalLayer: 'shade',
      blendMode: 'multiply',
      // Slightly stronger tip presence; softness drives the soft vanish.
      flow: 0.48,
      softness: 0.86,
      // Understated graphite grain — tonal blending first.
      textureIntensity: 0.1,
      garmentMask: true,
    }
  }
  return {
    brushKind: 'airbrush',
    logicalLayer: 'shade',
    blendMode: 'multiply',
    flow: 0.35,
    softness: 0.75,
    textureIntensity: 0,
    garmentMask: true,
  }
}

export function defaultSizeForBrushKind(kind: BrushKind): number {
  return BRUSH_KIND_DEFAULT_SIZE_PX[kind] ?? BRUSH_KIND_DEFAULT_SIZE_PX.tapered
}

export function clamp01(n: number, fallback = 0): number {
  if (!Number.isFinite(n)) return fallback
  return Math.min(1, Math.max(0, n))
}

export function resolveBrushKind(stroke: Pick<Stroke, 'brushKind' | 'tool'>): BrushKind {
  if (stroke.tool === 'erase') return 'tapered'
  const k = stroke.brushKind
  return k === 'charcoal' || k === 'airbrush' || k === 'tapered' ? k : 'tapered'
}

export function resolveLogicalLayer(
  stroke: Pick<Stroke, 'logicalLayer' | 'brushKind' | 'tool' | 'blendMode'>,
): LogicalLayer {
  if (stroke.logicalLayer === 'ink' || stroke.logicalLayer === 'shade' || stroke.logicalLayer === 'highlight') {
    return stroke.logicalLayer
  }
  // Legacy erase punches everything (handled separately); draw defaults by kind.
  if (stroke.tool === 'erase') return 'ink'
  const kind = resolveBrushKind(stroke)
  if (kind === 'tapered') return 'ink'
  if (stroke.blendMode === 'screen' || stroke.blendMode === 'soft-light') return 'highlight'
  return 'shade'
}

export function resolveBlendMode(stroke: Pick<Stroke, 'blendMode' | 'tool'>): StrokeBlendMode {
  if (stroke.tool === 'erase') return 'source-over'
  const m = stroke.blendMode
  return m === 'multiply' || m === 'soft-light' || m === 'screen' || m === 'source-over'
    ? m
    : 'source-over'
}

/** Stable 32-bit hash for deterministic charcoal grain. */
export function hashSeed(seed: string): number {
  let h = 2166136261 >>> 0
  for (let i = 0; i < seed.length; i += 1) {
    h ^= seed.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function pointsAsTriples(points: number[]): Array<{ x: number; y: number; p: number }> {
  const out: Array<{ x: number; y: number; p: number }> = []
  for (let i = 0; i < points.length; i += 3) {
    const x = points[i]
    const y = points[i + 1]
    const p = points[i + 2] ?? 0.5
    if (x === undefined || y === undefined) continue
    out.push({ x, y, p })
  }
  return out
}

function resamplePolyline(
  pts: Array<{ x: number; y: number; p: number }>,
  spacing: number,
): Array<{ x: number; y: number; p: number }> {
  if (pts.length === 0) return []
  if (pts.length === 1) return [pts[0]!]
  const out: Array<{ x: number; y: number; p: number }> = [pts[0]!]
  let carry = 0
  for (let i = 1; i < pts.length; i += 1) {
    const a = pts[i - 1]!
    const b = pts[i]!
    const dx = b.x - a.x
    const dy = b.y - a.y
    const dist = Math.hypot(dx, dy)
    if (dist < 1e-6) continue
    let t = (spacing - carry) / dist
    while (t <= 1) {
      const x = a.x + dx * t
      const y = a.y + dy * t
      const p = a.p + (b.p - a.p) * t
      out.push({ x, y, p })
      t += spacing / dist
    }
    carry = dist - (Math.floor((dist + carry) / spacing) * spacing - carry)
    // simpler carry for next segment:
    const used = Math.floor((dist + (spacing - carry > spacing ? 0 : spacing - carry)) / spacing)
    void used
    carry = (carry + dist) % spacing
  }
  return out
}

/** Compact resample: place stamps every `spacing` along the path. */
export function stampCenters(
  points: number[],
  spacing: number,
): Array<{ x: number; y: number; p: number }> {
  const pts = pointsAsTriples(points)
  if (pts.length === 0) return []
  if (pts.length === 1) return pts
  const out: Array<{ x: number; y: number; p: number }> = []
  let remaining = 0
  out.push(pts[0]!)
  for (let i = 1; i < pts.length; i += 1) {
    const a = pts[i - 1]!
    const b = pts[i]!
    let dx = b.x - a.x
    let dy = b.y - a.y
    let dist = Math.hypot(dx, dy)
    if (dist < 1e-6) continue
    let traveled = remaining
    while (traveled + spacing <= dist) {
      traveled += spacing
      const t = traveled / dist
      out.push({
        x: a.x + dx * t,
        y: a.y + dy * t,
        p: a.p + (b.p - a.p) * t,
      })
    }
    remaining = dist - traveled
    if (remaining < 0) remaining = 0
  }
  const last = pts[pts.length - 1]!
  const prev = out[out.length - 1]
  if (!prev || Math.hypot(last.x - prev.x, last.y - prev.y) > spacing * 0.35) {
    out.push(last)
  }
  return out
}

/** Even arc-length samples for width-ribbon charcoal (reuses stampCenters). */
export function evenArcSamples(
  pts: Array<{ x: number; y: number; p: number }>,
  spacing: number,
): Array<{ x: number; y: number; p: number }> {
  const flat: number[] = []
  for (const p of pts) flat.push(p.x, p.y, p.p)
  return stampCenters(flat, spacing)
}

type Ctx2d = CanvasRenderingContext2D

function paintTapered(ctx: Ctx2d, stroke: Stroke, sealTips?: boolean): void {
  const path = strokeToSvgPath(stroke, sealTips ? { sealTips: true } : undefined)
  if (!path) return
  const p = new Path2D(path)
  ctx.save()
  ctx.globalCompositeOperation = resolveBlendMode(stroke)
  ctx.globalAlpha = stroke.opacity
  ctx.fillStyle = stroke.color
  ctx.fill(p)
  ctx.restore()
}

/** Legacy stamp charcoal (renderer 1) — preserved for already-saved strokes. */
function paintCharcoalV1(ctx: Ctx2d, stroke: Stroke): void {
  const intensity = clamp01(stroke.textureIntensity ?? 0.32, 0.32)
  const flow = clamp01(stroke.flow ?? 0.38, 0.38)
  const softness = clamp01(stroke.softness ?? 0.78, 0.78)
  const seedStr = String(stroke.textureSeed ?? stroke.id)
  const rnd = mulberry32(hashSeed(seedStr))
  const spacing = Math.max(0.85, stroke.size * (0.12 + (1 - softness) * 0.1))
  const stamps = stampCenters(stroke.points, spacing)
  const blend = resolveBlendMode(stroke)
  const radius = Math.max(1.4, stroke.size * (0.95 + softness * 0.55))

  ctx.save()
  ctx.globalCompositeOperation = blend
  for (const s of stamps) {
    const press = 0.42 + s.p * 0.58
    const r = radius * (0.78 + press * 0.3)
    const alpha = Math.min(
      1,
      stroke.opacity * flow * (0.1 + press * 0.18) * (0.7 + softness * 0.35),
    )
    const mid = 0.22 + softness * 0.48
    const g = ctx.createRadialGradient(s.x, s.y, 0, s.x, s.y, r)
    g.addColorStop(0, hexWithAlpha(stroke.color, 1))
    g.addColorStop(Math.min(0.82, mid), hexWithAlpha(stroke.color, 0.42))
    g.addColorStop(1, hexWithAlpha(stroke.color, 0))
    ctx.globalAlpha = alpha
    ctx.fillStyle = g
    ctx.beginPath()
    ctx.arc(s.x, s.y, r, 0, Math.PI * 2)
    ctx.fill()
    if (intensity > 0.04) {
      const grains = Math.floor(3 + intensity * 8 + r * 0.22)
      for (let i = 0; i < grains; i += 1) {
        const ang = rnd() * Math.PI * 2
        const dist = Math.pow(rnd(), 0.7) * r * 0.62
        const gx = s.x + Math.cos(ang) * dist
        const gy = s.y + Math.sin(ang) * dist
        const gr = 0.28 + rnd() * (0.45 + intensity * 0.35)
        ctx.globalAlpha = alpha * (0.06 + intensity * 0.12) * press
        ctx.fillStyle = stroke.color
        ctx.beginPath()
        ctx.arc(gx, gy, gr, 0, Math.PI * 2)
        ctx.fill()
      }
    }
  }
  ctx.restore()
}

function averagePressure(pts: Array<{ x: number; y: number; p: number }>): number {
  if (pts.length === 0) return 0.5
  let sum = 0
  for (const p of pts) sum += p.p
  return sum / pts.length
}

/** Smooth polyline path for a continuous ribbon (quadratic midpoints). */
export function traceRibbonPath(
  ctx: Pick<Ctx2d, 'beginPath' | 'moveTo' | 'lineTo' | 'quadraticCurveTo'>,
  pts: Array<{ x: number; y: number; p: number }>,
): void {
  if (pts.length === 0) return
  ctx.beginPath()
  ctx.moveTo(pts[0]!.x, pts[0]!.y)
  if (pts.length === 1) return
  if (pts.length === 2) {
    ctx.lineTo(pts[1]!.x, pts[1]!.y)
    return
  }
  for (let i = 1; i < pts.length - 1; i += 1) {
    const cur = pts[i]!
    const next = pts[i + 1]!
    const mx = (cur.x + next.x) / 2
    const my = (cur.y + next.y) / 2
    ctx.quadraticCurveTo(cur.x, cur.y, mx, my)
  }
  const last = pts[pts.length - 1]!
  ctx.lineTo(last.x, last.y)
}

type CharcoalRibbonOpts = {
  intensity: number
  flow: number
  softness: number
  /** Narrow hard graphite core (pencil tip feel). */
  hardCore: boolean
  /** Fade from stroke tip → tail like lifting a pencil. */
  tipVanish: boolean
}

/**
 * Shared continuous charcoal ribbon. Density is independent of pointer sample rate
 * (full-path concentric passes). V2 = soft ribbon; V3 = hard tip + soft vanish.
 */
function paintCharcoalRibbon(ctx: Ctx2d, stroke: Stroke, opts: CharcoalRibbonOpts): void {
  const pts = pointsAsTriples(stroke.points)
  if (pts.length === 0) return

  const press = averagePressure(pts)
  const tipPress = pts[0]?.p ?? press
  const blend = resolveBlendMode(stroke)
  const softness = opts.softness
  const intensity = opts.intensity
  // Tip pressure firms the graphite core; average pressure still scales body width.
  const coreBoost = opts.hardCore ? 0.55 + tipPress * 0.45 : 0.5 + press * 0.5
  const baseW = Math.max(1.1, stroke.size * (opts.hardCore ? 0.38 + tipPress * 0.28 : coreBoost))
  const feather = baseW * (
    opts.hardCore
      ? 0.9 + softness * 1.75 + intensity * 0.2
      : 0.55 + softness * 1.35 + intensity * 0.25
  )
  const pad = Math.ceil(feather + baseW + 4)

  let minX = pts[0]!.x
  let minY = pts[0]!.y
  let maxX = minX
  let maxY = minY
  for (const p of pts) {
    minX = Math.min(minX, p.x)
    minY = Math.min(minY, p.y)
    maxX = Math.max(maxX, p.x)
    maxY = Math.max(maxY, p.y)
  }
  const ox = minX - pad
  const oy = minY - pad
  const mw = Math.max(1, Math.ceil(maxX - minX + pad * 2))
  const mh = Math.max(1, Math.ceil(maxY - minY + pad * 2))

  const mask = document.createElement('canvas')
  mask.width = mw
  mask.height = mh
  const mctx = mask.getContext('2d')
  if (!mctx) return

  mctx.translate(-ox, -oy)
  mctx.strokeStyle = '#ffffff'
  mctx.fillStyle = '#ffffff'
  mctx.lineCap = 'round'
  mctx.lineJoin = 'round'

  if (pts.length === 1) {
    const p = pts[0]!
    const steps = Math.max(6, Math.round(5 + softness * 10))
    for (let i = steps; i >= 0; i -= 1) {
      const t = i / steps
      // Hard bright core, long soft vanish outward (pencil tip on paper).
      const r = opts.hardCore
        ? baseW * (0.22 + (1 - t) * 0.45) + feather * t
        : baseW * (0.35 + (1 - t) * 0.65) + feather * t
      const a = opts.hardCore
        ? Math.pow(1 - t, 2.35)
        : Math.pow(1 - t * 0.95, 1.7)
      const g = mctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, Math.max(0.5, r))
      g.addColorStop(0, `rgba(255,255,255,${Math.min(1, a * (opts.hardCore ? 1.15 : 1))})`)
      if (opts.hardCore) {
        g.addColorStop(0.18, `rgba(255,255,255,${Math.min(1, a * 0.85)})`)
        g.addColorStop(0.55, `rgba(255,255,255,${a * 0.28})`)
      }
      g.addColorStop(1, 'rgba(255,255,255,0)')
      mctx.globalAlpha = 1
      mctx.fillStyle = g
      mctx.beginPath()
      mctx.arc(p.x, p.y, Math.max(0.5, r), 0, Math.PI * 2)
      mctx.fill()
    }
  } else {
    const steps = Math.max(7, Math.round(6 + softness * 11))
    for (let i = steps; i >= 0; i -= 1) {
      const t = i / steps // 1 = outer feather, 0 = hard tip/core
      const width = opts.hardCore
        ? baseW * (0.28 + (1 - t) * 0.42) + feather * t
        : baseW * (0.42 + (1 - t) * 0.58) + feather * t
      // Harder core curve: stays dense near center, vanishes faster toward edge.
      const a = opts.hardCore
        ? Math.pow(1 - t, 2.15) * (0.55 + tipPress * 0.45)
        : Math.pow(1 - t * 0.93, 1.55)
      mctx.globalAlpha = Math.min(1, a)
      mctx.lineWidth = Math.max(0.75, width)
      traceRibbonPath(mctx, pts)
      mctx.stroke()
    }
  }

  // Pencil lift: tip stays present, mark vanishes toward the stroke end.
  if (opts.tipVanish && pts.length > 1) {
    const tip = pts[0]!
    const tail = pts[pts.length - 1]!
    const dx = tip.x - tail.x
    const dy = tip.y - tail.y
    if (dx * dx + dy * dy > 4) {
      const fade = document.createElement('canvas')
      fade.width = mw
      fade.height = mh
      const fctx = fade.getContext('2d')
      if (fctx) {
        fctx.translate(-ox, -oy)
        const g = fctx.createLinearGradient(tip.x, tip.y, tail.x, tail.y)
        // Tip (start) hard → mid soft → end nearly gone.
        g.addColorStop(0, 'rgba(255,255,255,1)')
        g.addColorStop(0.28, 'rgba(255,255,255,0.92)')
        g.addColorStop(0.62, 'rgba(255,255,255,0.42)')
        g.addColorStop(1, 'rgba(255,255,255,0.04)')
        fctx.fillStyle = g
        // Expand slightly so feathered sides are covered.
        fctx.fillRect(ox - 2, oy - 2, mw + 4, mh + 4)
        mctx.setTransform(1, 0, 0, 1, 0, 0)
        mctx.globalCompositeOperation = 'destination-in'
        mctx.globalAlpha = 1
        mctx.drawImage(fade, 0, 0)
        mctx.globalCompositeOperation = 'source-over'
        mctx.translate(-ox, -oy)
      }
    }
  }

  const tint = document.createElement('canvas')
  tint.width = mw
  tint.height = mh
  const tctx = tint.getContext('2d')
  if (!tctx) return
  tctx.fillStyle = stroke.color
  tctx.fillRect(0, 0, mw, mh)
  tctx.globalCompositeOperation = 'destination-in'
  tctx.drawImage(mask, 0, 0)

  ctx.save()
  ctx.globalCompositeOperation = blend
  // One final alpha — independent of how many pointer samples were recorded.
  const body = opts.hardCore ? 0.7 + tipPress * 0.35 : 0.62 + press * 0.38
  ctx.globalAlpha = clamp01(stroke.opacity * opts.flow * body, 0.55)
  ctx.drawImage(tint, ox, oy)
  ctx.restore()
}

/** Charcoal V2 — continuous soft ribbon (saved strokes with renderer 2). */
function paintCharcoalV2(ctx: Ctx2d, stroke: Stroke): void {
  paintCharcoalRibbon(ctx, stroke, {
    intensity: clamp01(stroke.textureIntensity ?? 0.14, 0.14),
    flow: clamp01(stroke.flow ?? 0.42, 0.42),
    softness: clamp01(stroke.softness ?? 0.82, 0.82),
    hardCore: false,
    tipVanish: false,
  })
}

/**
 * Charcoal V3 — tip→tail lift (saved renderer 3). Prefer V4 for new work.
 */
function paintCharcoalV3(ctx: Ctx2d, stroke: Stroke): void {
  paintCharcoalRibbon(ctx, stroke, {
    intensity: clamp01(stroke.textureIntensity ?? 0.1, 0.1),
    flow: clamp01(stroke.flow ?? 0.48, 0.48),
    softness: clamp01(stroke.softness ?? 0.86, 0.86),
    hardCore: true,
    tipVanish: true,
  })
}

/** Unit left-normal for a segment (points left of travel direction). */
export function segmentLeftNormal(
  ax: number,
  ay: number,
  bx: number,
  by: number,
): { nx: number; ny: number } {
  const dx = bx - ax
  const dy = by - ay
  const len = Math.hypot(dx, dy)
  if (len < 1e-6) return { nx: 0, ny: 0 }
  return { nx: -dy / len, ny: dx / len }
}

/**
 * Smooth per-vertex normals for an open polyline (averaged left-normals).
 * Soft side = left of travel. Flip with `side` (-1 = right of travel).
 */
export function polylineSideNormals(
  pts: Array<{ x: number; y: number }>,
  side = 1,
): Array<{ nx: number; ny: number }> {
  if (pts.length === 0) return []
  if (pts.length === 1) return [{ nx: side, ny: 0 }]
  const out: Array<{ nx: number; ny: number }> = []
  for (let i = 0; i < pts.length; i += 1) {
    const prev = pts[Math.max(0, i - 1)]!
    const next = pts[Math.min(pts.length - 1, i + 1)]!
    const n = segmentLeftNormal(prev.x, prev.y, next.x, next.y)
    const len = Math.hypot(n.nx, n.ny)
    if (len < 1e-6) {
      out.push({ nx: 0, ny: 0 })
    } else {
      out.push({ nx: (n.nx / len) * side, ny: (n.ny / len) * side })
    }
  }
  return out
}

/**
 * Charcoal V4 — solid stroke with width gradient.
 *
 * Hard dark edge along the path (pencil tip edge), soft vanish across the
 * width only — density stays consistent along the stroke length. Built from
 * even arc-length quads so pointer sample rate cannot blotch the mark.
 */
function paintCharcoalV4(ctx: Ctx2d, stroke: Stroke): void {
  const intensity = clamp01(stroke.textureIntensity ?? 0.1, 0.1)
  const flow = clamp01(stroke.flow ?? 0.48, 0.48)
  const softness = clamp01(stroke.softness ?? 0.86, 0.86)
  const pts = pointsAsTriples(stroke.points)
  if (pts.length === 0) return

  const press = averagePressure(pts)
  const blend = resolveBlendMode(stroke)
  // Narrow hard edge + soft width controlled by size/softness.
  const hardW = Math.max(0.9, stroke.size * (0.14 + press * 0.1))
  const softWidth = Math.max(
    hardW * 2.2,
    stroke.size * (0.85 + softness * 1.15 + intensity * 0.2) * (0.55 + press * 0.45),
  )
  const pad = Math.ceil(softWidth + hardW + 6)

  let minX = pts[0]!.x
  let minY = pts[0]!.y
  let maxX = minX
  let maxY = minY
  for (const p of pts) {
    minX = Math.min(minX, p.x)
    minY = Math.min(minY, p.y)
    maxX = Math.max(maxX, p.x)
    maxY = Math.max(maxY, p.y)
  }
  const ox = minX - pad
  const oy = minY - pad
  const mw = Math.max(1, Math.ceil(maxX - minX + pad * 2))
  const mh = Math.max(1, Math.ceil(maxY - minY + pad * 2))

  const mask = document.createElement('canvas')
  mask.width = mw
  mask.height = mh
  const mctx = mask.getContext('2d')
  if (!mctx) return
  mctx.translate(-ox, -oy)

  if (pts.length === 1) {
    // Single tap: hard center → soft half-disk vanish (angled tip feel).
    const p = pts[0]!
    const g = mctx.createLinearGradient(p.x, p.y, p.x + softWidth, p.y)
    g.addColorStop(0, 'rgba(255,255,255,1)')
    g.addColorStop(0.12, 'rgba(255,255,255,0.95)')
    g.addColorStop(0.45, 'rgba(255,255,255,0.35)')
    g.addColorStop(1, 'rgba(255,255,255,0)')
    mctx.fillStyle = g
    mctx.beginPath()
    mctx.arc(p.x, p.y, softWidth, 0, Math.PI * 2)
    mctx.fill()
  } else {
    // Even spacing along path — independent of pointer density / speed.
    const spacing = Math.max(1.6, hardW * 0.85)
    const spaced = evenArcSamples(pts, spacing)
    const ribbon = spaced.length >= 2 ? spaced : pts
    // Soft side = right of travel (screen-right for a downward vertical fold).
    const normals = polylineSideNormals(ribbon, -1)

    mctx.strokeStyle = '#ffffff'
    mctx.lineCap = 'round'
    mctx.lineJoin = 'round'

    // Width gradient: full-path offset ribbons (outer soft → near hard edge).
    // One stroke per offset — no along-path overdraw / no segment banding.
    const steps = Math.max(8, Math.round(7 + softness * 10))
    for (let i = steps; i >= 1; i -= 1) {
      const t = i / steps // 1 = far soft edge, ~0 = near hard edge
      const offset = softWidth * t
      const alpha = Math.pow(1 - t, 1.85) * 0.9
      const width = Math.max(1.1, hardW * 0.55 + softWidth * 0.22 * (1 - t))
      const offsetPts = ribbon.map((p, idx) => {
        const n = normals[idx]!
        return {
          x: p.x + n.nx * offset,
          y: p.y + n.ny * offset,
          p: p.p,
        }
      })
      mctx.globalAlpha = Math.min(1, alpha)
      mctx.lineWidth = width
      traceRibbonPath(mctx, offsetPts)
      mctx.stroke()
    }

    // Crisp hard edge along the tip path (solid graphite line).
    mctx.globalAlpha = 1
    mctx.lineWidth = Math.max(1.1, hardW)
    traceRibbonPath(mctx, ribbon)
    mctx.stroke()

    // Tiny understated grain only inside soft width (never spray outside).
    if (intensity > 0.05) {
      const seedStr = String(stroke.textureSeed ?? stroke.id)
      const rnd = mulberry32(hashSeed(seedStr))
      const grains = Math.min(40, Math.floor(ribbon.length * intensity * 1.1))
      for (let g = 0; g < grains; g += 1) {
        const idx = Math.min(ribbon.length - 1, Math.floor(rnd() * ribbon.length))
        const p = ribbon[idx]!
        const n = normals[idx]!
        const across = 0.18 + rnd() * 0.65
        const gx = p.x + n.nx * softWidth * across
        const gy = p.y + n.ny * softWidth * across
        mctx.globalAlpha = (0.035 + intensity * 0.07) * (1 - across)
        mctx.fillStyle = '#ffffff'
        mctx.beginPath()
        mctx.arc(gx, gy, 0.3 + rnd() * 0.45, 0, Math.PI * 2)
        mctx.fill()
      }
      mctx.globalAlpha = 1
    }
  }

  const tint = document.createElement('canvas')
  tint.width = mw
  tint.height = mh
  const tctx = tint.getContext('2d')
  if (!tctx) return
  tctx.fillStyle = stroke.color
  tctx.fillRect(0, 0, mw, mh)
  tctx.globalCompositeOperation = 'destination-in'
  tctx.drawImage(mask, 0, 0)

  ctx.save()
  ctx.globalCompositeOperation = blend
  ctx.globalAlpha = clamp01(stroke.opacity * flow * (0.68 + press * 0.32), 0.55)
  ctx.drawImage(tint, ox, oy)
  ctx.restore()
}

function resolveCharcoalRenderer(stroke: Stroke): number {
  const v = stroke.charcoalRenderer
  if (v === CHARCOAL_RENDERER_V1) return CHARCOAL_RENDERER_V1
  if (v === CHARCOAL_RENDERER_V2) return CHARCOAL_RENDERER_V2
  if (v === CHARCOAL_RENDERER_V3) return CHARCOAL_RENDERER_V3
  if (v === CHARCOAL_RENDERER_V4) return CHARCOAL_RENDERER_V4
  // Absent on legacy charcoal → keep stamp look for saved artwork.
  if (stroke.brushKind === 'charcoal' && v == null) return CHARCOAL_RENDERER_V1
  return CHARCOAL_RENDERER_CURRENT
}

function paintCharcoal(ctx: Ctx2d, stroke: Stroke): void {
  const renderer = resolveCharcoalRenderer(stroke)
  if (renderer === CHARCOAL_RENDERER_V1) {
    paintCharcoalV1(ctx, stroke)
    return
  }
  if (renderer === CHARCOAL_RENDERER_V2) {
    paintCharcoalV2(ctx, stroke)
    return
  }
  if (renderer === CHARCOAL_RENDERER_V3) {
    paintCharcoalV3(ctx, stroke)
    return
  }
  paintCharcoalV4(ctx, stroke)
}

function paintAirbrush(ctx: Ctx2d, stroke: Stroke): void {
  const softness = clamp01(stroke.softness ?? DEFAULT_SOFTNESS, DEFAULT_SOFTNESS)
  const flow = clamp01(stroke.flow ?? DEFAULT_FLOW, DEFAULT_FLOW)
  const spacing = Math.max(1.5, stroke.size * (0.22 + softness * 0.18))
  const stamps = stampCenters(stroke.points, spacing)
  const blend = resolveBlendMode(stroke)
  const radius = Math.max(1, stroke.size * (0.85 + softness * 0.6))

  ctx.save()
  ctx.globalCompositeOperation = blend

  for (const s of stamps) {
    const press = 0.4 + s.p * 0.6
    const r = radius * (0.75 + press * 0.35)
    // V2-0024: slightly stronger stamp presence so live draft doesn’t vanish on soft airbrush.
    const alpha = Math.min(
      1,
      stroke.opacity * flow * (0.28 + press * 0.34) * (0.62 + softness * 0.42),
    )
    const g = ctx.createRadialGradient(s.x, s.y, 0, s.x, s.y, r)
    const mid = 0.35 + softness * 0.4
    const edge = hexWithAlpha(stroke.color, 0)
    const core = hexWithAlpha(stroke.color, 1)
    g.addColorStop(0, core)
    g.addColorStop(Math.min(0.92, mid), hexWithAlpha(stroke.color, 0.62))
    g.addColorStop(1, edge)
    ctx.globalAlpha = alpha
    ctx.fillStyle = g
    ctx.beginPath()
    ctx.arc(s.x, s.y, r, 0, Math.PI * 2)
    ctx.fill()
  }
  ctx.restore()
}

function hexWithAlpha(hex: string, alpha: number): string {
  const raw = hex.replace('#', '')
  if (raw.length !== 6) return `rgba(0,0,0,${alpha})`
  const r = Number.parseInt(raw.slice(0, 2), 16)
  const g = Number.parseInt(raw.slice(2, 4), 16)
  const b = Number.parseInt(raw.slice(4, 6), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

export function paintEraseOnContext(ctx: Ctx2d, stroke: Stroke): void {
  if (stroke.tool !== 'erase') return
  const path = strokeToSvgPath(stroke)
  if (!path) return
  const p = new Path2D(path)
  ctx.save()
  ctx.globalCompositeOperation = 'destination-out'
  ctx.fillStyle = 'rgba(0,0,0,1)'
  ctx.fill(p)
  ctx.restore()
}

export type ProfessionalPaintOptions = {
  sealTips?: boolean
  /** Same design-space transform as `ctx`; used when stroke.garmentMask is true. */
  garmentAlpha?: HTMLCanvasElement | null
}

function paintDrawWithOptionalGarmentClip(
  ctx: Ctx2d,
  stroke: Stroke,
  garmentAlpha: HTMLCanvasElement | null | undefined,
  paint: (target: Ctx2d) => void,
): void {
  if (!stroke.garmentMask || !garmentAlpha) {
    paint(ctx)
    return
  }
  const w = ctx.canvas.width
  const h = ctx.canvas.height
  if (w <= 0 || h <= 0) {
    paint(ctx)
    return
  }
  const tmp = document.createElement('canvas')
  tmp.width = w
  tmp.height = h
  const t = tmp.getContext('2d')
  if (!t) {
    paint(ctx)
    return
  }
  // Mirror the layer's design→output transform so stroke points land correctly,
  // then clip with garment alpha already rasterized in output space.
  const xform = ctx.getTransform()
  t.setTransform(xform)
  paint(t)
  t.setTransform(1, 0, 0, 1, 0, 0)
  t.globalCompositeOperation = 'destination-in'
  t.drawImage(garmentAlpha, 0, 0)
  ctx.save()
  ctx.setTransform(1, 0, 0, 1, 0, 0)
  ctx.drawImage(tmp, 0, 0)
  ctx.restore()
}

/**
 * Paint one draw stroke with the professional brush engine.
 * Erase strokes should use paintEraseOnContext on the target layer.
 */
export function paintProfessionalDrawStroke(
  ctx: Ctx2d,
  stroke: Stroke,
  options?: ProfessionalPaintOptions,
): void {
  if (stroke.tool !== 'draw') return
  const kind = resolveBrushKind(stroke)
  const garmentAlpha = options?.garmentAlpha
  if (kind === 'charcoal') {
    paintDrawWithOptionalGarmentClip(ctx, stroke, garmentAlpha, (c) => paintCharcoal(c, stroke))
    return
  }
  if (kind === 'airbrush') {
    paintDrawWithOptionalGarmentClip(ctx, stroke, garmentAlpha, (c) => paintAirbrush(c, stroke))
    return
  }
  paintTapered(ctx, stroke, options?.sealTips === true)
}

/**
 * Whether an erase stroke should punch garment fills (legacy + ink-layer erasers).
 * Shade/highlight erasers must not destroy base fabric fills.
 */
export function erasePunchesFills(stroke: Stroke): boolean {
  if (stroke.tool !== 'erase') return false
  // Explicit legacy: no logicalLayer → keep historical fill punch.
  if (stroke.logicalLayer == null) return true
  return stroke.logicalLayer === 'ink'
}

/**
 * Whether erase should affect a given logical paint layer.
 * Legacy erasers (no logicalLayer) punch all layers (historical ink behavior).
 */
export function eraseAffectsLayer(stroke: Stroke, layer: LogicalLayer): boolean {
  if (stroke.tool !== 'erase') return false
  if (stroke.logicalLayer == null) return true
  return stroke.logicalLayer === layer
}

export type PaintInkOptions = {
  sealTips?: boolean
}

/**
 * Paint chronological draw+erase onto a single canvas (legacy single-ink stack).
 * Prefer paintLogicalArtworkLayers for non-destructive shade/highlight isolation.
 */
export function paintInkStrokesProfessional(
  ctx: Ctx2d,
  strokes: Stroke[],
  options?: PaintInkOptions,
): void {
  const sealTips = options?.sealTips === true
  for (const stroke of strokes) {
    if (stroke.tool === 'erase') {
      paintEraseOnContext(ctx, stroke)
      continue
    }
    if (stroke.tool === 'draw') {
      // For fill barriers (sealTips), only tapered geometry matters — skip soft brushes.
      if (sealTips && resolveBrushKind(stroke) !== 'tapered') continue
      paintProfessionalDrawStroke(ctx, stroke, { sealTips })
    }
  }
}

export type LogicalLayerCanvases = {
  shade: HTMLCanvasElement
  ink: HTMLCanvasElement
  highlight: HTMLCanvasElement
}

/**
 * Build separate shade → ink → highlight canvases so erasers can target one layer.
 * Draw order for composite: shade, then ink, then highlight.
 */
export function paintLogicalArtworkLayers(
  width: number,
  height: number,
  strokes: Stroke[],
  options?: {
    sealTips?: boolean
    originX?: number
    originY?: number
    scaleX?: number
    scaleY?: number
    offsetX?: number
    offsetY?: number
    /** When provided, charcoal/airbrush strokes with garmentMask clip to fill alpha. */
    fills?: FillOp[]
  },
): LogicalLayerCanvases {
  const make = (): { canvas: HTMLCanvasElement; ctx: Ctx2d } | null => {
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext('2d')
    if (!ctx) return null
    const sx = options?.scaleX ?? 1
    const sy = options?.scaleY ?? 1
    const ox = options?.originX ?? 0
    const oy = options?.originY ?? 0
    const offX = options?.offsetX ?? 0
    const offY = options?.offsetY ?? 0
    if (offX !== 0 || offY !== 0) ctx.translate(offX, offY)
    if (sx !== 1 || sy !== 1) ctx.scale(sx, sy)
    if (ox !== 0 || oy !== 0) ctx.translate(-ox, -oy)
    return { canvas, ctx }
  }

  const shade = make()
  const ink = make()
  const highlight = make()
  if (!shade || !ink || !highlight) {
    throw new Error('Canvas 2D unavailable')
  }
  const sealTips = options?.sealTips === true

  let garmentAlpha: HTMLCanvasElement | null = null
  const fills = options?.fills
  const needsMask = Boolean(
    fills &&
      fills.length > 0 &&
      strokes.some((s) => s.tool === 'draw' && s.garmentMask === true),
  )
  if (needsMask && fills) {
    const g = make()
    if (g) {
      paintFillOps(g.ctx, fills)
      garmentAlpha = g.canvas
    }
  }

  const layerCtx = (layer: LogicalLayer): Ctx2d => {
    if (layer === 'shade') return shade.ctx
    if (layer === 'highlight') return highlight.ctx
    return ink.ctx
  }

  for (const stroke of strokes) {
    if (stroke.tool === 'erase') {
      for (const layer of LOGICAL_LAYERS) {
        if (eraseAffectsLayer(stroke, layer)) paintEraseOnContext(layerCtx(layer), stroke)
      }
      continue
    }
    if (stroke.tool !== 'draw') continue
    if (sealTips && resolveBrushKind(stroke) !== 'tapered') continue
    const layer = resolveLogicalLayer(stroke)
    paintProfessionalDrawStroke(layerCtx(layer), stroke, { sealTips, garmentAlpha })
  }

  return { shade: shade.canvas, ink: ink.canvas, highlight: highlight.canvas }
}

export function compositeLogicalLayers(
  target: Ctx2d,
  layers: LogicalLayerCanvases,
  width: number,
  height: number,
): void {
  target.drawImage(layers.shade, 0, 0, width, height)
  target.drawImage(layers.ink, 0, 0, width, height)
  target.drawImage(layers.highlight, 0, 0, width, height)
}

/** Attach professional fields onto a new stroke from engine state. */
export function applyBrushEngineToStroke(
  stroke: Stroke,
  engine: BrushEngineState,
): Stroke {
  if (stroke.tool === 'erase') {
    return {
      ...stroke,
      brushKind: 'tapered',
      logicalLayer: engine.logicalLayer,
      blendMode: 'source-over',
      garmentMask: false,
    }
  }
  return {
    ...stroke,
    brushKind: engine.brushKind,
    logicalLayer: engine.logicalLayer,
    blendMode: engine.blendMode,
    flow: engine.flow,
    softness: engine.softness,
    textureIntensity: engine.textureIntensity,
    textureSeed: stroke.textureSeed ?? stroke.id,
    // Keep key order aligned with pickProfessionalFields (charcoalRenderer before garmentMask).
    charcoalRenderer:
      engine.brushKind === 'charcoal' ? CHARCOAL_RENDERER_CURRENT : stroke.charcoalRenderer,
    garmentMask: engine.garmentMask === true,
  }
}

/** Parse optional professional fields from a raw stroke object (lenient). */
export function pickProfessionalFields(raw: Record<string, unknown>): Partial<Stroke> {
  const out: Partial<Stroke> = {}
  if (raw.brushKind === 'tapered' || raw.brushKind === 'charcoal' || raw.brushKind === 'airbrush') {
    out.brushKind = raw.brushKind
  }
  if (raw.logicalLayer === 'ink' || raw.logicalLayer === 'shade' || raw.logicalLayer === 'highlight') {
    out.logicalLayer = raw.logicalLayer
  }
  if (
    raw.blendMode === 'source-over' ||
    raw.blendMode === 'multiply' ||
    raw.blendMode === 'soft-light' ||
    raw.blendMode === 'screen'
  ) {
    out.blendMode = raw.blendMode
  }
  if (typeof raw.flow === 'number' && Number.isFinite(raw.flow)) {
    out.flow = clamp01(raw.flow, DEFAULT_FLOW)
  }
  if (typeof raw.softness === 'number' && Number.isFinite(raw.softness)) {
    out.softness = clamp01(raw.softness, DEFAULT_SOFTNESS)
  }
  if (typeof raw.textureIntensity === 'number' && Number.isFinite(raw.textureIntensity)) {
    out.textureIntensity = clamp01(raw.textureIntensity, DEFAULT_TEXTURE_INTENSITY)
  }
  if (typeof raw.textureSeed === 'string' || typeof raw.textureSeed === 'number') {
    out.textureSeed = raw.textureSeed
  }
  if (typeof raw.charcoalRenderer === 'number' && Number.isFinite(raw.charcoalRenderer)) {
    out.charcoalRenderer = Math.floor(raw.charcoalRenderer)
  }
  if (typeof raw.garmentMask === 'boolean') {
    out.garmentMask = raw.garmentMask
  }
  return out
}

/** Avoid unused helper lint if resample kept for tests. */
export const __test = {
  resamplePolyline,
  mulberry32,
  hashSeed,
  paintCharcoalV1,
  paintCharcoalV2,
  paintCharcoalV3,
  paintCharcoalV4,
  resolveCharcoalRenderer,
  averagePressure,
}
