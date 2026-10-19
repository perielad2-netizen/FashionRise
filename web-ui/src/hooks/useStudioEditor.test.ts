import { describe, expect, it } from 'vitest'
import { nearestBrushSizeId } from '@/hooks/useStudioEditor'
import { BRUSH_SIZES } from '@/lib/strokes'

describe('nearestBrushSizeId', () => {
  it('snaps continuous sizes to the existing brush system', () => {
    expect(nearestBrushSizeId(2)).toBe('thin')
    expect(nearestBrushSizeId(BRUSH_SIZES.medium)).toBe('medium')
    expect(nearestBrushSizeId(12)).toBe('bold')
  })
})
