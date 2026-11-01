import { describe, expect, it } from 'vitest'
import { fitContainDestRect } from '@/lib/croquisGeometry'
import { DESIGN_HEIGHT, DESIGN_WIDTH } from '@/lib/strokes'

describe('croquisGeometry fit-contain (production underlay helper)', () => {
  it('letterboxes tall sources into 768×1024 without cropping height', () => {
    const r = fitContainDestRect(400, 2000)
    expect(r.h).toBeCloseTo(DESIGN_HEIGHT)
    expect(r.w).toBeLessThan(DESIGN_WIDTH)
    expect(r.x + r.w).toBeLessThanOrEqual(DESIGN_WIDTH + 1e-6)
    expect(r.y).toBeCloseTo(0)
  })

  it('pillarboxes wide sources into 768×1024 without cropping width', () => {
    const r = fitContainDestRect(2000, 400)
    expect(r.w).toBeCloseTo(DESIGN_WIDTH)
    expect(r.h).toBeLessThan(DESIGN_HEIGHT)
    expect(r.y + r.h).toBeLessThanOrEqual(DESIGN_HEIGHT + 1e-6)
  })
})
