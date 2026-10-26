import { describe, expect, it } from 'vitest'
import { bumpDraftDocument, createEmptyDraftDocument } from '@/lib/draftDocument'
import { buildSharedGarmentSpec, paletteFromDoc } from '@/services/ai/magicGarmentSpec'

describe('magicGarmentSpec palette priority', () => {
  it('prioritizes applied pink fill over black outline and unused brush swatch', () => {
    let doc = createEmptyDraftDocument()
    doc = bumpDraftDocument(doc, {
      schema: 'fashionrise.studio.draft.v2',
      model: 'female-straight',
      brush: { sizeId: 'thin', sizePx: 1.75, opacity: 1, color: '#111111' },
      strokes: [
        {
          id: 'outline',
          tool: 'draw',
          points: [10, 20, 0.5, 30, 40, 0.5],
          color: '#1C1C1E',
          size: 1.75,
          opacity: 1,
        },
      ],
      fills: [
        {
          id: 'pink-fill',
          contour: [100, 100, 200, 100, 200, 200, 100, 200],
          style: { kind: 'solid', color: '#FF2D95' },
          seedX: 150,
          seedY: 150,
        },
      ],
      back: {
        strokes: [
          {
            id: 'back-outline',
            tool: 'draw',
            points: [12, 22, 0.5, 32, 42, 0.5],
            color: '#000000',
            size: 1.75,
            opacity: 1,
          },
        ],
        fills: [
          {
            id: 'back-pink',
            contour: [110, 110, 210, 110, 210, 210, 110, 210],
            style: { kind: 'solid', color: '#E6007A' },
            seedX: 160,
            seedY: 160,
          },
        ],
      },
    })

    const { colors, main_colors } = paletteFromDoc(doc)
    expect(main_colors[0]).toBe('#FF2D95')
    expect(main_colors).toContain('#E6007A')
    expect(main_colors[0]).not.toBe('#1C1C1E')
    expect(main_colors[0]).not.toBe('#111111')
    expect(main_colors[0]).not.toBe('#000000')
    // Outline colors may appear later in the full palette, never ahead of fills in main_colors.
    expect(colors.indexOf('#FF2D95')).toBeLessThan(colors.indexOf('#1C1C1E'))

    const spec = buildSharedGarmentSpec(doc, 'polish concept')
    expect(spec.main_colors?.[0]).toBe('#FF2D95')
    expect(spec.main_colors).toEqual(expect.arrayContaining(['#FF2D95', '#E6007A']))
  })

  it('does not treat unused selected brush color as applied garment material', () => {
    let doc = createEmptyDraftDocument()
    doc = bumpDraftDocument(doc, {
      brush: { sizeId: 'thin', sizePx: 1.75, opacity: 1, color: '#FF00AA' },
      strokes: [
        {
          id: 's1',
          tool: 'draw',
          points: [1, 2, 0.5, 3, 4, 0.5],
          color: '#222222',
          size: 1.75,
          opacity: 1,
        },
      ],
      fills: [],
    })
    const { colors, main_colors } = paletteFromDoc(doc)
    expect(colors).not.toContain('#FF00AA')
    expect(main_colors).toEqual(['#222222'])
  })

  it('uses gradient fill stops in main_colors ahead of outline ink', () => {
    let doc = createEmptyDraftDocument()
    doc = bumpDraftDocument(doc, {
      brush: { sizeId: 'thin', sizePx: 1.75, opacity: 1, color: '#000000' },
      strokes: [
        {
          id: 's1',
          tool: 'draw',
          points: [1, 2, 0.5, 3, 4, 0.5],
          color: '#111111',
          size: 1.75,
          opacity: 1,
        },
      ],
      fills: [
        {
          id: 'g1',
          contour: [0, 0, 10, 0, 10, 10, 0, 10],
          style: { kind: 'gradient', gradientId: 'sunset', colors: ['#FF6B9D', '#FFC2D4'], angle: 90 },
          seedX: 5,
          seedY: 5,
        },
      ],
    })
    const { main_colors } = paletteFromDoc(doc)
    expect(main_colors.slice(0, 2)).toEqual(['#FF6B9D', '#FFC2D4'])
  })

  it('uses built-in pink satin fabric color in main_colors, not black outline', () => {
    let doc = createEmptyDraftDocument()
    doc = bumpDraftDocument(doc, {
      brush: { sizeId: 'thin', sizePx: 1.75, opacity: 1, color: '#111111' },
      strokes: [
        {
          id: 'outline',
          tool: 'draw',
          points: [10, 20, 0.5, 30, 40, 0.5],
          color: '#1C1C1E',
          size: 1.75,
          opacity: 1,
        },
      ],
      fills: [
        {
          id: 'satin-pink',
          contour: [100, 100, 200, 100, 200, 200, 100, 200],
          style: { kind: 'fabric', fabricId: 'satin' },
          seedX: 150,
          seedY: 150,
        },
      ],
    })
    const { colors, main_colors } = paletteFromDoc(doc)
    expect(main_colors[0]).toBe('#BE185D')
    expect(main_colors[0]).not.toBe('#1C1C1E')
    expect(main_colors[0]).not.toBe('#111111')
    expect(colors.indexOf('#BE185D')).toBeLessThan(colors.indexOf('#1C1C1E'))

    const spec = buildSharedGarmentSpec(doc)
    expect(spec.main_colors?.[0]).toBe('#BE185D')
    expect(spec.materials?.[0]).toMatch(/Satin repeating textile/i)
    expect(spec.materials?.[0]).toMatch(/exact Studio tile/i)
  })

  it('does not invent a hex color for uploaded fabric', () => {
    let doc = createEmptyDraftDocument()
    doc = bumpDraftDocument(doc, {
      brush: { sizeId: 'thin', sizePx: 1.75, opacity: 1, color: '#111111' },
      strokes: [
        {
          id: 'outline',
          tool: 'draw',
          points: [10, 20, 0.5, 30, 40, 0.5],
          color: '#222222',
          size: 1.75,
          opacity: 1,
        },
      ],
      fills: [
        {
          id: 'up',
          contour: [100, 100, 200, 100, 200, 200, 100, 200],
          style: {
            kind: 'uploaded-fabric',
            assetId: 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
            scale: 1,
          },
          seedX: 150,
          seedY: 150,
        },
      ],
    })
    const { main_colors } = paletteFromDoc(doc)
    expect(main_colors).toEqual(['#222222'])
    const spec = buildSharedGarmentSpec(doc)
    expect(spec.materials).toEqual([
      'uploaded fabric repeating textile (exact Studio tile reference)',
    ])
    expect(spec.main_colors).toEqual(['#222222'])
  })
})
