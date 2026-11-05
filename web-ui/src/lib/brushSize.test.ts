import { describe, expect, it } from 'vitest'
import {
  BRUSH_SIZE_DEFAULT_PX,
  BRUSH_SIZE_MAX_PX,
  BRUSH_SIZE_MIN_PX,
  BRUSH_SIZES,
  clampBrushSizePx,
  formatBrushSizePx,
  nearestBrushSizeId,
  resolveBrushSizePx,
  snapBrushSizePx,
} from '@/lib/strokes'

describe('brush size numeric helpers', () => {
  it('clamps and snaps to 0.25 px increments', () => {
    expect(snapBrushSizePx(6.5)).toBe(6.5)
    expect(snapBrushSizePx(12.75)).toBe(12.75)
    expect(snapBrushSizePx(1.25)).toBe(1.25)
    expect(snapBrushSizePx(30)).toBe(30)
    expect(snapBrushSizePx(0.1)).toBe(BRUSH_SIZE_MIN_PX)
    expect(snapBrushSizePx(99)).toBe(BRUSH_SIZE_MAX_PX)
    expect(snapBrushSizePx(1.13)).toBe(1.25)
  })

  it('preserves the thin default', () => {
    expect(BRUSH_SIZE_DEFAULT_PX).toBe(1.75)
    expect(clampBrushSizePx(Number.NaN)).toBe(1.75)
  })

  it('maps nearest legacy ids without forcing new sizes onto presets', () => {
    expect(nearestBrushSizeId(6.5)).toBe('thick')
    expect(nearestBrushSizeId(1.75)).toBe('thin')
    expect(nearestBrushSizeId(12.75)).toBe('bold')
  })

  it('resolves legacy sizeId when sizePx is absent', () => {
    expect(resolveBrushSizePx({ sizeId: 'medium' })).toBe(BRUSH_SIZES.medium)
    expect(resolveBrushSizePx({ sizeId: 'thin', sizePx: 6.5 })).toBe(6.5)
  })

  it('formats display values cleanly', () => {
    expect(formatBrushSizePx(1.25)).toBe('1.25')
    expect(formatBrushSizePx(30)).toBe('30')
    expect(formatBrushSizePx(12.75)).toBe('12.75')
  })
})
