/**
 * Professional Sketch Engine V1 — brush kinds, logical layers, Canvas2D paint.
 * Deterministic charcoal (seeded). Tapered ink stays perfect-freehand SVG.
 */

import { strokeToSvgPath } from '@/lib/freehand'
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

/** Suggested defaults when switching brush kind. */
export function defaultsForBrushKind(kind: BrushKind): Partial<BrushEngineState> {
  if (kind === 'tapered') {
    return {
      brushKind: 'tapered',
      logicalLayer: 'ink',
      blendMode: 'source-over',
      flow: 1,
      softness: 0.2,
      textureIntensity: 0,
    }
  }
  if (kind === 'charcoal') {
    return {
      brushKind: 'charcoal',
      logicalLayer: 'shade',
      blendMode: 'multiply',
      flow: 0.38,
      softness: 0.78,
      // Fine paper grain only — not spray scatter.
      textureIntensity: 0.32,
    }
  }
  return {
    brushKind: 'airbrush',
    logicalLayer: 'shade',
    blendMode: 'multiply',
    flow: 0.35,
    softness: 0.75,
    textureIntensity: 0,
  }
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

/**
 * Charcoal = soft fashion-illustration shading (blending-stump feel),
 * not spray/smoke. Continuous soft radial build-up + optional fine grain
 * constrained inside each dab. Deterministic via textureSeed.
 */
function paintCharcoal(ctx: Ctx2d, stroke: Stroke): void {
  const intensity = clamp01(stroke.textureIntensity ?? 0.32, 0.32)
  const flow = clamp01(stroke.flow ?? 0.38, 0.38)
  const softness = clamp01(stroke.softness ?? 0.78, 0.78)
  const seedStr = String(stroke.textureSeed ?? stroke.id)
  const rnd = mulberry32(hashSeed(seedStr))
  // Tight spacing so dabs melt into a smooth shadow ribbon.
  const spacing = Math.max(0.85, stroke.size * (0.12 + (1 - softness) * 0.1))
  const stamps = stampCenters(stroke.points, spacing)
  const blend = resolveBlendMode(stroke)
  const radius = Math.max(1.4, stroke.size * (0.95 + softness * 0.55))

  ctx.save()
  ctx.globalCompositeOperation = blend

  for (const s of stamps) {
    const press = 0.42 + s.p * 0.58
    const r = radius * (0.78 + press * 0.3)
    // Low per-dab alpha → overlaps blend into soft volume, not blotches.
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

    // Subtle paper grain only — tiny dots, center-biased, never wide scatter.
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
    const alpha = Math.min(1, stroke.opacity * flow * (0.18 + press * 0.28) * (0.55 + softness * 0.45))
    const g = ctx.createRadialGradient(s.x, s.y, 0, s.x, s.y, r)
    const mid = 0.35 + softness * 0.4
    const edge = hexWithAlpha(stroke.color, 0)
    const core = hexWithAlpha(stroke.color, 1)
    g.addColorStop(0, core)
    g.addColorStop(Math.min(0.92, mid), hexWithAlpha(stroke.color, 0.55))
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

/**
 * Paint one draw stroke with the professional brush engine.
 * Erase strokes should use paintEraseOnContext on the target layer.
 */
export function paintProfessionalDrawStroke(
  ctx: Ctx2d,
  stroke: Stroke,
  options?: { sealTips?: boolean },
): void {
  if (stroke.tool !== 'draw') return
  const kind = resolveBrushKind(stroke)
  if (kind === 'charcoal') {
    paintCharcoal(ctx, stroke)
    return
  }
  if (kind === 'airbrush') {
    paintAirbrush(ctx, stroke)
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
    paintProfessionalDrawStroke(layerCtx(layer), stroke, { sealTips })
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
  return out
}

/** Avoid unused helper lint if resample kept for tests. */
export const __test = { resamplePolyline, mulberry32, hashSeed }
