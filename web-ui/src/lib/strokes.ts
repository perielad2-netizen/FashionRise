export type ToolKind = 'draw' | 'erase' | 'fill' | 'eyedropper'

export type Stroke = {
  id: string
  tool: ToolKind
  /** Flattened [x,y,pressure?, ...] points in design space (768×1024). */
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
