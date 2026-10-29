export type ToolKind = 'draw' | 'erase' | 'fill' | 'eyedropper'

export type Stroke = {
  id: string
  tool: ToolKind
  /**
   * Flattened [x,y,pressure?, ...] points in design space.
   * Legacy croquis reference remains 768×1024; extended paper allows coordinates
   * outside that plane (see `paperBounds.ts`).
   */
  points: number[]
  color: string
  size: number
  opacity: number
}

export type BrushSizeId = 'thin' | 'medium' | 'thick' | 'bold'

/** Design-space sizes on the 768×1024 canvas. Thin/medium stay pencil-fine. */
export const BRUSH_SIZES: Record<BrushSizeId, number> = {
  thin: 1.75,
  medium: 3.5,
  thick: 7,
  bold: 13,
}

/** Continuous brush size range (design-space px). Legacy presets remain for compatibility. */
export const BRUSH_SIZE_MIN_PX = 0.5
export const BRUSH_SIZE_MAX_PX = 40
export const BRUSH_SIZE_STEP_PX = 0.25
/** Matches former thin preset — default studio brush. */
export const BRUSH_SIZE_DEFAULT_PX = BRUSH_SIZES.thin

export function clampBrushSizePx(px: number): number {
  if (!Number.isFinite(px)) return BRUSH_SIZE_DEFAULT_PX
  return Math.min(BRUSH_SIZE_MAX_PX, Math.max(BRUSH_SIZE_MIN_PX, px))
}

/** Snap to the configured increment after clamping (e.g. 6.5, 12.75). */
export function snapBrushSizePx(px: number): number {
  const clamped = clampBrushSizePx(px)
  const steps = Math.round(clamped / BRUSH_SIZE_STEP_PX)
  return clampBrushSizePx(steps * BRUSH_SIZE_STEP_PX)
}

/** Map a numeric size to the nearest legacy preset id (persistence compatibility only). */
export function nearestBrushSizeId(px: number): BrushSizeId {
  const entries = Object.entries(BRUSH_SIZES) as [BrushSizeId, number][]
  let best: BrushSizeId = 'medium'
  let bestDist = Number.POSITIVE_INFINITY
  for (const [id, size] of entries) {
    const dist = Math.abs(size - px)
    if (dist < bestDist) {
      best = id
      bestDist = dist
    }
  }
  return best
}

export function resolveBrushSizePx(brush: {
  sizeId: BrushSizeId
  sizePx?: number | null
}): number {
  if (typeof brush.sizePx === 'number' && Number.isFinite(brush.sizePx) && brush.sizePx > 0) {
    return snapBrushSizePx(brush.sizePx)
  }
  return BRUSH_SIZES[brush.sizeId] ?? BRUSH_SIZE_DEFAULT_PX
}

export function formatBrushSizePx(px: number): string {
  const n = snapBrushSizePx(px)
  if (Number.isInteger(n)) return String(n)
  return n.toFixed(2).replace(/\.?0+$/, '')
}

export const INK_SWATCHES = [
  { id: 'ink', label: 'Ink', color: '#1C1C1E' },
  { id: 'navy', label: 'Navy', color: '#1E3A8A' },
  { id: 'pink', label: 'Pink', color: '#D63384' },
  { id: 'burgundy', label: 'Burgundy', color: '#9F1239' },
  { id: 'grey', label: 'Grey', color: '#6B7280' },
] as const

export const DESIGN_WIDTH = 768
export const DESIGN_HEIGHT = 1024

export function createStrokeId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `stroke_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
}

export function cloneStrokes(strokes: Stroke[]): Stroke[] {
  return strokes.map((s) => ({ ...s, points: [...s.points] }))
}
