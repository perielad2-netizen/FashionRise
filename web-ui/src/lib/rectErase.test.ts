import { describe, expect, it } from 'vitest'
import type { FillOp } from '@/lib/fills'
import type { Stroke } from '@/lib/strokes'
import {
  eraseArtworkInRect,
  fillHitsRect,
  isMeaningfulPaperRect,
  normalizePaperRect,
  strokeHitsRect,
} from '@/lib/rectErase'

function stroke(partial: Partial<Stroke> & Pick<Stroke, 'id' | 'points'>): Stroke {
  return {
    tool: 'draw',
    color: '#111111',
    size: 4,
    opacity: 1,
    ...partial,
  }
}

function fill(contour: number[]): FillOp {
  return {
    id: 'f1',
    style: { kind: 'solid', color: '#FF0000' },
    contour,
    seedX: contour[0]!,
    seedY: contour[1]!,
  }
}

describe('rectErase (V2-0030)', () => {
  it('normalizes drag corners into a positive AABB', () => {
    expect(normalizePaperRect({ x: 10, y: 20 }, { x: 4, y: 8 })).toEqual({
      x: 4,
      y: 8,
      width: 6,
      height: 12,
    })
  })

  it('rejects tiny taps as non-meaningful selections', () => {
    expect(isMeaningfulPaperRect({ x: 0, y: 0, width: 2, height: 100 })).toBe(false)
    expect(isMeaningfulPaperRect({ x: 0, y: 0, width: 8, height: 8 })).toBe(true)
  })

  it('detects stroke and fill hits inside the selection', () => {
    const s = stroke({ id: 's1', points: [10, 10, 0.5, 20, 20, 0.5] })
    expect(strokeHitsRect(s, { x: 15, y: 15, width: 20, height: 20 })).toBe(true)
    expect(strokeHitsRect(s, { x: 100, y: 100, width: 10, height: 10 })).toBe(false)

    const f = fill([0, 0, 50, 0, 50, 50, 0, 50])
    expect(fillHitsRect(f, { x: 40, y: 40, width: 20, height: 20 })).toBe(true)
    expect(fillHitsRect(f, { x: 200, y: 200, width: 10, height: 10 })).toBe(false)
  })

  it('removes intersecting ink strokes and fills; preserves outside artwork', () => {
    const inside = stroke({ id: 'in', points: [12, 12, 1, 18, 18, 1] })
    const outside = stroke({ id: 'out', points: [200, 200, 1, 220, 220, 1] })
    const fillIn = fill([10, 10, 30, 10, 30, 30, 10, 30])
    fillIn.id = 'fin'
    const fillOut = fill([180, 180, 220, 180, 220, 220, 180, 220])
    fillOut.id = 'fout'

    const next = eraseArtworkInRect(
      { strokes: [inside, outside], fills: [fillIn, fillOut] },
      { x: 8, y: 8, width: 40, height: 40 },
      { logicalLayer: 'ink' },
    )
    expect(next.changed).toBe(true)
    expect(next.strokes.map((s) => s.id)).toEqual(['out'])
    expect(next.fills.map((f) => f.id)).toEqual(['fout'])
  })

  it('shade-layer rect erase does not delete fills or ink strokes', () => {
    const ink = stroke({ id: 'ink', points: [10, 10, 1, 20, 20, 1], logicalLayer: 'ink' })
    const shade = stroke({
      id: 'shade',
      points: [12, 12, 1, 18, 18, 1],
      logicalLayer: 'shade',
      brushKind: 'charcoal',
    })
    const f = fill([8, 8, 40, 8, 40, 40, 8, 40])
    const next = eraseArtworkInRect(
      { strokes: [ink, shade], fills: [f] },
      { x: 5, y: 5, width: 40, height: 40 },
      { logicalLayer: 'shade' },
    )
    expect(next.changed).toBe(true)
    expect(next.strokes.map((s) => s.id)).toEqual(['ink'])
    expect(next.fills).toHaveLength(1)
  })

  it('no-ops when nothing intersects', () => {
    const s = stroke({ id: 's', points: [0, 0, 1, 5, 5, 1] })
    const next = eraseArtworkInRect(
      { strokes: [s], fills: [] },
      { x: 400, y: 400, width: 20, height: 20 },
    )
    expect(next.changed).toBe(false)
    expect(next.strokes).toHaveLength(1)
  })
})
