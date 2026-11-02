import { describe, expect, it } from 'vitest'
import { buildTryOnDesignHints, detectTrouserLegFills } from '@/lib/tryOnDesignHints'
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

  it('adds jumpsuit/narrow-leg hints when two lower fills are clear', () => {
    const fills: FillOp[] = [
      {
        id: 'bodice',
        contour: [300, 80, 460, 80, 460, 420, 300, 420],
        seedX: 380,
        seedY: 240,
        style: { kind: 'solid', color: '#166534' },
      },
      {
        id: 'leftLeg',
        contour: [300, 500, 360, 500, 360, 900, 300, 900],
        seedX: 330,
        seedY: 700,
        style: { kind: 'solid', color: '#166534' },
      },
      {
        id: 'rightLeg',
        contour: [400, 500, 460, 500, 460, 900, 400, 900],
        seedX: 430,
        seedY: 700,
        style: { kind: 'solid', color: '#166534' },
      },
    ]
    const detected = detectTrouserLegFills(fills)
    expect(detected.looksLikeTrousers).toBe(true)
    expect(detected.looksLikeJumpsuit).toBe(true)
    const hints = buildTryOnDesignHints({ strokes: [], fills })
    expect(hints.some((h) => /jumpsuit/i.test(h))).toBe(true)
    expect(hints.some((h) => /separate/i.test(h))).toBe(true)
    expect(hints.some((h) => /skirt panel/i.test(h))).toBe(true)
  })

  it('does not inject trousers hints for a dress/skirt fill', () => {
    const fills: FillOp[] = [
      {
        id: 'dress',
        contour: [200, 100, 560, 100, 600, 900, 160, 900],
        seedX: 380,
        seedY: 500,
        style: { kind: 'solid', color: '#B91C1C' },
      },
    ]
    expect(detectTrouserLegFills(fills).looksLikeTrousers).toBe(false)
    const hints = buildTryOnDesignHints({ strokes: [], fills })
    expect(hints.some((h) => /jumpsuit|trousers|pant legs/i.test(h))).toBe(false)
  })

  it('does not inject trousers hints for swimsuit-like high fills', () => {
    const fills: FillOp[] = [
      {
        id: 'swim',
        contour: [320, 120, 448, 120, 480, 420, 288, 420],
        seedX: 380,
        seedY: 260,
        style: { kind: 'solid', color: '#0E7490' },
      },
    ]
    expect(detectTrouserLegFills(fills).looksLikeTrousers).toBe(false)
  })

  it('keeps trouser geometry hints inside the 8-hint budget (#172)', () => {
    const fills: FillOp[] = [
      {
        id: 'bodice',
        contour: [300, 80, 460, 80, 460, 420, 300, 420],
        seedX: 380,
        seedY: 240,
        style: { kind: 'solid', color: '#166534' },
      },
      {
        id: 'leftLeg',
        contour: [300, 500, 360, 500, 360, 900, 300, 900],
        seedX: 330,
        seedY: 700,
        style: { kind: 'solid', color: '#166534' },
      },
      {
        id: 'rightLeg',
        contour: [400, 500, 460, 500, 460, 900, 400, 900],
        seedX: 430,
        seedY: 700,
        style: { kind: 'solid', color: '#166534' },
      },
      // Extra fills that would previously crowd out geometry hints.
      ...Array.from({ length: 6 }, (_, i) => ({
        id: `extra-${i}`,
        contour: [10 + i * 20, 20, 40 + i * 20, 20, 40 + i * 20, 50, 10 + i * 20, 50],
        seedX: 20 + i * 20,
        seedY: 30,
        style: { kind: 'solid' as const, color: `#${(0x111111 * (i + 1)).toString(16).padStart(6, '0')}` },
      })),
    ]
    const strokes: Stroke[] = [
      stroke({ id: 'hat', points: [100, 40, 0.5, 140, 60, 0.5], color: '#222222' }),
      stroke({ id: 's2', points: [200, 50, 0.5, 240, 70, 0.5], color: '#ABCDEF' }),
    ]
    const hints = buildTryOnDesignHints({ strokes, fills })
    expect(hints.length).toBeLessThanOrEqual(8)
    expect(hints.some((h) => /jumpsuit/i.test(h))).toBe(true)
    expect(hints.some((h) => /separate/i.test(h))).toBe(true)
    expect(hints.some((h) => /skirt panel/i.test(h))).toBe(true)
  })
})
