import getStroke from 'perfect-freehand'
import type { Stroke } from '@/lib/strokes'

export type PointInput = {
  x: number
  y: number
  pressure?: number
}

/** Convert stroke points array into perfect-freehand input tuples. */
export function toFreehandInput(points: number[]): number[][] {
  const out: number[][] = []
  for (let i = 0; i < points.length; i += 3) {
    const x = points[i]
    const y = points[i + 1]
    const p = points[i + 2] ?? 0.5
    if (x === undefined || y === undefined) continue
    out.push([x, y, p])
  }
  return out
}

export function appendPoint(points: number[], point: PointInput): number[] {
  return [...points, point.x, point.y, point.pressure ?? 0.5]
}

export function strokeToSvgPath(stroke: Stroke): string {
  const input = toFreehandInput(stroke.points)
  if (input.length === 0) return ''

  const outline = getStroke(input, {
    size: stroke.size,
    thinning: stroke.tool === 'erase' ? 0.4 : 0.55,
    smoothing: 0.55,
    streamline: 0.45,
    easing: (t) => t,
    start: { taper: 0, cap: true },
    end: { taper: stroke.size * 0.35, cap: true },
  })

  return getSvgPathFromStroke(outline)
}

/** Convert freehand polygon outline to SVG path string. */
export function getSvgPathFromStroke(points: number[][]): string {
  if (!points.length) return ''
  const d = points.reduce(
    (acc, point, i, arr) => {
      const [x0, y0] = point
      const [x1, y1] = arr[(i + 1) % arr.length]!
      acc.push(x0!, y0!, (x0! + x1!) / 2, (y0! + y1!) / 2)
      return acc
    },
    ['M', points[0]![0]!, points[0]![1]!, 'Q'] as (string | number)[],
  )
  d.push('Z')
  return d.join(' ')
}
