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

function pressureSpread(points: number[]): number {
  let min = 1
  let max = 0
  let count = 0
  for (let i = 2; i < points.length; i += 3) {
    const p = points[i] ?? 0.5
    min = Math.min(min, p)
    max = Math.max(max, p)
    count += 1
  }
  if (count === 0) return 0
  return max - min
}

export function strokeToSvgPath(stroke: Stroke): string {
  const input = toFreehandInput(stroke.points)
  if (input.length === 0) return ''

  const erase = stroke.tool === 'erase'
  // Flat mouse pressure gets velocity simulation; a real pen already varies pressure.
  const simulatePressure = !erase && pressureSpread(stroke.points) < 0.08

  const outline = getStroke(input, {
    size: erase ? Math.max(stroke.size * 2.4, 10) : stroke.size,
    thinning: erase ? 0.15 : 0.72,
    smoothing: erase ? 0.4 : 0.68,
    streamline: erase ? 0.35 : 0.58,
    simulatePressure,
    easing: (t) => (erase ? t : Math.sin((t * Math.PI) / 2)),
    start: { taper: erase ? 0 : Math.max(6, stroke.size * 2.2), cap: true },
    end: { taper: erase ? 0 : Math.max(10, stroke.size * 3.2), cap: true },
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
