import { describe, expect, it } from 'vitest'
import { strokeToSvgPath } from '@/lib/freehand'
import type { Stroke } from '@/lib/strokes'

function denseLine(x0: number, y0: number, x1: number, y1: number, n = 24): number[] {
  const out: number[] = []
  for (let i = 0; i <= n; i += 1) {
    const t = i / n
    out.push(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, 0.5)
  }
  return out
}

describe('strokeToSvgPath sealTips (#127)', () => {
  it('produces a path for thin draw strokes with and without sealTips', () => {
    const stroke: Stroke = {
      id: 't',
      tool: 'draw',
      points: denseLine(40, 100, 120, 100),
      color: '#111',
      size: 1.75,
      opacity: 1,
    }
    const visual = strokeToSvgPath(stroke)
    const sealed = strokeToSvgPath(stroke, { sealTips: true })
    expect(visual.startsWith('M')).toBe(true)
    expect(sealed.startsWith('M')).toBe(true)
    expect(visual).not.toEqual(sealed)
  })
})
