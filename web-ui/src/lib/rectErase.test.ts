import { describe, expect, it } from 'vitest'
import type { FillOp } from '@/lib/fills'
import type { Stroke } from '@/lib/strokes'
import {
  clipPolylineOutsideRect,
  eraseArtworkInRect,
  fillHitsRect,
  isMeaningfulPaperRect,
  normalizePaperRect,
  segmentCrossesOrEntersRect,
  strokeHitsRect,
} from '@/lib/rectErase'

function stroke(partial: Partial<Stroke> & Pick<Stroke, 'id' | 'points'>): Stroke {
  return {
    tool: 'draw',
    color: '#111111',
    size: 2,
    opacity: 1,
    ...partial,
  }
}

function fill(contour: number[], id = 'f1'): FillOp {
  return {
    id,
    style: { kind: 'solid', color: '#FF0000' },
    contour,
    seedX: contour[0]!,
    seedY: contour[1]!,
  }
}

describe('rectErase clip mode (V2-0030)', () => {
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

  it('detects a long stroke that crosses the selection with both endpoints outside', () => {
    // Horizontal line from x=0 to x=100 through rect [40,40]–[60,60] — neither end inside.
    expect(segmentCrossesOrEntersRect(0, 50, 100, 50, { x: 40, y: 40, width: 20, height: 20 })).toBe(
      true,
    )
    const s = stroke({
      id: 'cross',
      points: [0, 50, 1, 100, 50, 1],
      size: 1,
    })
    expect(
      strokeHitsRect(s, { x: 40, y: 40, width: 20, height: 20 }, { includeStrokeWidth: false }),
    ).toBe(true)
  })

  it('clips a long crossing stroke — exterior stubs remain, midsection erased', () => {
    const s = stroke({
      id: 'long',
      points: [0, 50, 1, 100, 50, 1],
      size: 1,
    })
    const next = eraseArtworkInRect(
      { strokes: [s], fills: [] },
      { x: 40, y: 40, width: 20, height: 20 },
      { logicalLayer: 'ink', includeStrokeWidth: false },
    )
    expect(next.changed).toBe(true)
    expect(next.strokes.length).toBeGreaterThanOrEqual(2)
    // Left stub ends near x=40; right stub starts near x=60.
    const left = next.strokes[0]!
    const right = next.strokes[next.strokes.length - 1]!
    expect(left.points[0]).toBeCloseTo(0, 0)
    expect(left.points[left.points.length - 3]!).toBeCloseTo(40, 0)
    expect(right.points[0]).toBeCloseTo(60, 0)
    expect(right.points[right.points.length - 3]!).toBeCloseTo(100, 0)
    // No sample point remains strictly inside the erase rect.
    for (const frag of next.strokes) {
      for (let i = 0; i + 1 < frag.points.length; i += 3) {
        const x = frag.points[i]!
        const y = frag.points[i + 1]!
        const inside = x > 40.5 && x < 59.5 && y > 40.5 && y < 59.5
        expect(inside).toBe(false)
      }
    }
  })

  it('preserves artwork completely outside the rectangle', () => {
    const outside = stroke({ id: 'out', points: [200, 200, 1, 220, 220, 1] })
    const fillOut = fill([180, 180, 220, 180, 220, 220, 180, 220], 'fout')
    const next = eraseArtworkInRect(
      { strokes: [outside], fills: [fillOut] },
      { x: 8, y: 8, width: 40, height: 40 },
      { logicalLayer: 'ink' },
    )
    expect(next.changed).toBe(false)
    expect(next.strokes).toHaveLength(1)
    expect(next.strokes[0]!.id).toBe('out')
    expect(next.fills).toHaveLength(1)
    expect(next.fills[0]!.id).toBe('fout')
  })

  it('partially overlapping fill keeps exterior via hole punch', () => {
    const f = fill([0, 0, 100, 0, 100, 100, 0, 100], 'big')
    expect(fillHitsRect(f, { x: 40, y: 40, width: 20, height: 20 })).toBe(true)
    const next = eraseArtworkInRect(
      { strokes: [], fills: [f] },
      { x: 40, y: 40, width: 20, height: 20 },
      { logicalLayer: 'ink' },
    )
    expect(next.changed).toBe(true)
    expect(next.fills).toHaveLength(1)
    expect(next.fills[0]!.contour).toEqual(f.contour)
    expect(next.fills[0]!.holes?.length).toBe(1)
    const hole = next.fills[0]!.holes![0]!
    // Hole matches erase rect corners.
    expect(hole[0]).toBeCloseTo(40, 5)
    expect(hole[1]).toBeCloseTo(40, 5)
  })

  it('shade-layer rect erase does not punch fills or ink strokes', () => {
    const ink = stroke({ id: 'ink', points: [10, 10, 1, 20, 20, 1], logicalLayer: 'ink' })
    const shade = stroke({
      id: 'shade',
      points: [0, 50, 1, 100, 50, 1],
      logicalLayer: 'shade',
      brushKind: 'charcoal',
      size: 1,
    })
    const f = fill([8, 8, 40, 8, 40, 40, 8, 40])
    const next = eraseArtworkInRect(
      { strokes: [ink, shade], fills: [f] },
      { x: 40, y: 40, width: 20, height: 20 },
      { logicalLayer: 'shade', includeStrokeWidth: false },
    )
    expect(next.changed).toBe(true)
    expect(next.strokes.some((s) => s.id === 'ink' || s.points === ink.points)).toBe(true)
    expect(next.fills).toHaveLength(1)
    expect(next.fills[0]!.holes).toBeUndefined()
    // Shade stroke was clipped (not wholesale deleted as the only outcome).
    expect(next.strokes.filter((s) => s.logicalLayer === 'shade').length).toBeGreaterThanOrEqual(1)
  })

  it('clipPolylineOutsideRect returns empty when the stroke is fully inside', () => {
    expect(
      clipPolylineOutsideRect([45, 45, 1, 50, 50, 1], { x: 40, y: 40, width: 20, height: 20 }),
    ).toEqual([])
  })
})
