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
    expect(spec.notes).toMatch(/polish concept/i)
    expect(spec.notes).toMatch(/polished professional fashion concept/i)
    expect(spec.notes).toMatch(/applied fill\/gradient\/fabric colors/i)
    expect(spec.notes).toMatch(/invent no accent colors/i)
    expect(spec.notes).toMatch(/uneven straps\/sleeves/i)
    expect(spec.notes).toMatch(/normalize sketch glitches/i)
    expect(spec.notes.length).toBeLessThanOrEqual(500)
    expect(spec.details).toMatch(/render=polished_professional_enhancement/)
    expect(spec.details).toMatch(/sketch_role=strong_guidance_not_pixel_trace/)
    expect(spec.details).toMatch(/color_authority=applied_fills_only/)
    expect(spec.details).toMatch(/sketch_cleanup=normalize_imperfections/)
  })

  it('gray-only applied fill keeps main_colors locked to gray (no invented accents in spec)', () => {
    let doc = createEmptyDraftDocument()
    doc = bumpDraftDocument(doc, {
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
          id: 'gray-fill',
          contour: [100, 100, 200, 100, 200, 200, 100, 200],
          style: { kind: 'solid', color: '#9CA3AF' },
          seedX: 150,
          seedY: 150,
        },
      ],
    })
    const { main_colors } = paletteFromDoc(doc)
    expect(main_colors).toEqual(['#9CA3AF'])
    expect(main_colors.join(' ')).not.toMatch(/FF|BE185D|0000FF|FF2D95/i)
    const spec = buildSharedGarmentSpec(doc, 'polish concept')
    expect(spec.main_colors).toEqual(['#9CA3AF'])
    expect(spec.notes).toMatch(/invent no accent colors/i)
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

  it('skips outline-ink solid fills and adds pale bridal notes (#183)', () => {
    let doc = createEmptyDraftDocument()
    doc = bumpDraftDocument(doc, {
      brush: { sizeId: 'thin', sizePx: 1.75, opacity: 1, color: '#111111' },
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
          id: 'outline-noise',
          contour: [10, 10, 30, 10, 30, 30, 10, 30],
          style: { kind: 'solid', color: '#111111' },
          seedX: 20,
          seedY: 20,
        },
        {
          id: 'gown',
          contour: [200, 80, 360, 80, 400, 200, 380, 900, 180, 900, 160, 200, 280, 260],
          style: { kind: 'gradient', gradientId: 'custom', colors: ['#F8F4F0', '#D4AF9B'], angle: 90 },
          seedX: 300,
          seedY: 500,
        },
        {
          id: 'leftSleeve',
          contour: [40, 120, 160, 120, 160, 320, 40, 320],
          style: { kind: 'solid', color: '#F8F4F0' },
          seedX: 100,
          seedY: 200,
        },
        {
          id: 'rightSleeve',
          contour: [600, 120, 720, 120, 720, 320, 600, 320],
          style: { kind: 'solid', color: '#F8F4F0' },
          seedX: 660,
          seedY: 200,
        },
      ],
    })
    const { main_colors } = paletteFromDoc(doc)
    expect(main_colors).not.toContain('#111111')
    expect(main_colors.some((c) => c === '#F8F4F0' || c === '#D4AF9B')).toBe(true)
    const spec = buildSharedGarmentSpec(doc)
    expect(spec.notes || '').toMatch(/pale|cream|ivory/i)
    expect(spec.notes || '').toMatch(/plunging|cleavage|open/i)
    expect(spec.notes || '').toMatch(/both.*sleeve/i)
    expect(spec.details || '').toMatch(/pale_bridal_fidelity=1/)
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
          // Garment-scale fill (~8% of design plane) — shoe-sized satin is ignored.
          contour: [100, 100, 350, 100, 350, 350, 100, 350],
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

  it('ignores shoe-scale satin fabric so ink stroke colors remain main', () => {
    let doc = createEmptyDraftDocument()
    doc = bumpDraftDocument(doc, {
      brush: { sizeId: 'thin', sizePx: 1.75, opacity: 1, color: '#6B8E23' },
      strokes: [
        {
          id: 'ink',
          tool: 'draw',
          points: [10, 20, 0.5, 30, 40, 0.5],
          color: '#6B8E23',
          size: 3,
          opacity: 1,
        },
      ],
      fills: [
        {
          id: 'shoe-satin',
          contour: [400, 900, 440, 900, 440, 940, 400, 940],
          style: { kind: 'fabric', fabricId: 'satin' },
          seedX: 420,
          seedY: 920,
        },
      ],
    })
    const { main_colors } = paletteFromDoc(doc)
    expect(main_colors[0]).toBe('#6B8E23')
    const spec = buildSharedGarmentSpec(doc)
    expect(spec.materials ?? []).toEqual([])
    expect(spec.main_colors?.[0]).toBe('#6B8E23')
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
          contour: [100, 100, 350, 100, 350, 350, 100, 350],
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
