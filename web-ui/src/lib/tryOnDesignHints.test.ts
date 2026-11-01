import { describe, expect, it } from 'vitest'
import { buildTryOnDesignHints } from '@/lib/tryOnDesignHints'
import type { FillOp } from '@/lib/fills'
import type { Stroke } from '@/lib/strokes'

function stroke(partial: Partial<Stroke> & { points: number[] }): Stroke {
  return {
    id: partial.id ?? 's1',
    tool: partial.tool ?? 'draw',
    color: partial.color ?? '#FF69B4',
    size: partial.size ?? 4,
    opacity: partial.opacity ?? 1,
    points: partial.points,
  }
}

describe('buildTryOnDesignHints', () => {
  it('emits color, print topology, and upper accessory hints', () => {
    const fills: FillOp[] = [
      {
        id: 'f1',
        contour: [10, 20, 40, 20, 40, 60, 10, 60],
        seedX: 20,
        seedY: 30,
        style: { kind: 'solid', color: '#FF69B4' },
      },
    ]
    const strokes: Stroke[] = [
      stroke({ id: 'hat', points: [100, 40, 0.5, 140, 60, 0.5], color: '#222222' }),
    ]
    const hints = buildTryOnDesignHints({ strokes, fills })
    expect(hints.some((h) => h.includes('#FF69B4'))).toBe(true)
    expect(hints.some((h) => /checkerboard|print topology/i.test(h))).toBe(true)
    expect(hints.some((h) => /hat\/cap/i.test(h))).toBe(true)
    expect(hints.length).toBeLessThanOrEqual(8)
  })

  it('mentions fabric presets when used', () => {
    const fills: FillOp[] = [
      {
        id: 'f2',
        contour: [12, 40, 80, 40, 80, 120, 12, 120],
        seedX: 40,
        seedY: 70,
        style: { kind: 'fabric', fabricId: 'floral' },
      },
    ]
    const hints = buildTryOnDesignHints({ strokes: [], fills })
    expect(hints.some((h) => /Floral repeating fabric fill/i.test(h))).toBe(true)
  })
})
