import { describe, expect, it } from 'vitest'
import { defaultFabricTileIds } from '@/lib/defaultFabricTiles'
import { FABRIC_PRESETS } from '@/lib/fills'

describe('defaultFabricTiles', () => {
  it('lists every image-backed starter fabric (12)', () => {
    const ids = defaultFabricTileIds()
    expect(ids).toEqual([
      'blue-denim',
      'white-silk',
      'black-cotton',
      'brown-corduroy',
      'blush-chiffon',
      'charcoal-wool',
      'gold-glitter',
      'blue-velvet',
      'wedding-lace',
      'offwhite-satin',
      'stockings',
      'stitch-jeans',
    ])
    expect(ids).toHaveLength(12)
    for (const id of ids) {
      const preset = FABRIC_PRESETS.find((p) => p.id === id)
      expect(preset?.tileUrl).toMatch(/^\/fabrics\/defaults\/.+\.png$/)
      expect(preset?.fallbackColor).toMatch(/^#[0-9A-Fa-f]{6}$/)
    }
  })
})
