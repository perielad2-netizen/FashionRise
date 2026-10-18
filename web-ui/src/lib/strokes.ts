export type ToolKind = 'draw' | 'erase'

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

export const BRUSH_SIZES: Record<BrushSizeId, number> = {
  thin: 2,
  medium: 5,
  thick: 10,
  bold: 18,
}

export const INK_SWATCHES = [
  { id: 'ink', label: 'Ink', color: '#1C1C1E' },
  { id: 'navy', label: 'Navy', color: '#1E3A8A' },
  { id: 'pink', label: 'Pink', color: '#EC4899' },
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
