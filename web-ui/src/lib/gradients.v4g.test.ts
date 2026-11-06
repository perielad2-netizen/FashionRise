import { describe, expect, it } from 'vitest'
import {
  CUSTOM_GRADIENT_ID,
  GRADIENT_PRESETS,
  LEGACY_GRADIENT_IDS,
  customGradientStyle,
  gradientCssAngle,
  gradientPreviewCss,
  gradientStyleFromPreset,
  parseFillOp,
} from '@/lib/fills'

describe('WEB-V4G gradients', () => {
  it('keeps original four preset ids and exact color/angle values', () => {
    expect(LEGACY_GRADIENT_IDS).toEqual([
      'rose-violet',
      'champagne',
      'ocean-blush',
      'noir-wine',
    ])
    expect(gradientStyleFromPreset('rose-violet')).toEqual({
      kind: 'gradient',
      gradientId: 'rose-violet',
      colors: ['#D63384', '#7C3AED'],
      angle: 135,
    })
    expect(GRADIENT_PRESETS.find((g) => g.id === 'rose-violet')?.preview).toBe(
      'linear-gradient(135deg,#d63384,#7c3aed)',
    )
  })

  it('expands the library with distinct fashion presets', () => {
    expect(GRADIENT_PRESETS.length).toBeGreaterThanOrEqual(12)
    expect(GRADIENT_PRESETS.length).toBeLessThanOrEqual(16)
    const ids = new Set(GRADIENT_PRESETS.map((g) => g.id))
    expect(ids.size).toBe(GRADIENT_PRESETS.length)
    expect(ids.has('rose-gold')).toBe(true)
    expect(ids.has('black-cherry')).toBe(true)
  })

  it('builds self-contained custom gradients and rejects bad HEX', () => {
    const ok = customGradientStyle(['#ff00aa', '#112233'], 45)
    expect(ok).toEqual({
      kind: 'gradient',
      gradientId: CUSTOM_GRADIENT_ID,
      colors: ['#FF00AA', '#112233'],
      angle: 45,
    })
    expect(customGradientStyle(['nope', '#112233'], 10)).toBeNull()
  })

  it('maps canvas angles to CSS preview degrees consistently', () => {
    expect(gradientCssAngle(0)).toBe(90)
    expect(gradientCssAngle(90)).toBe(180)
    expect(gradientPreviewCss(['#111111', '#FFFFFF'], 0)).toBe(
      'linear-gradient(90deg,#111111,#FFFFFF)',
    )
  })

  it('parses historical and custom gradient fills without rewriting history', () => {
    const historical = parseFillOp({
      id: 'h1',
      contour: [0, 0, 20, 0, 20, 20, 0, 20],
      style: {
        kind: 'gradient',
        gradientId: 'rose-violet',
        colors: ['#d63384', '#7c3aed'],
        angle: 135,
      },
      seedX: 5,
      seedY: 5,
    })
    expect(historical?.style).toEqual({
      kind: 'gradient',
      gradientId: 'rose-violet',
      colors: ['#D63384', '#7C3AED'],
      angle: 135,
    })

    const custom = parseFillOp({
      contour: [0, 0, 30, 0, 30, 30, 0, 30],
      style: {
        kind: 'gradient',
        gradientId: 'custom',
        colors: ['#abcdef', '#010203'],
        angle: 200,
      },
      seedX: 10,
      seedY: 10,
    })
    expect(custom?.style).toMatchObject({
      kind: 'gradient',
      gradientId: 'custom',
      colors: ['#ABCDEF', '#010203'],
      angle: 200,
    })
  })
})
