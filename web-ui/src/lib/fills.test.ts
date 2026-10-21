import { describe, expect, it } from 'vitest'
import {
  cloneFills,
  contourToSvgPath,
  FABRIC_PRESETS,
  fabricStyle,
  gradientStyleFromPreset,
  parseFillOp,
  solidStyle,
} from '@/lib/fills'

describe('fills schema', () => {
  it('parses solid, gradient and fabric fills', () => {
    const solid = parseFillOp({
      id: 'f1',
      contour: [10, 10, 40, 10, 40, 40, 10, 40],
      style: { kind: 'solid', color: '#b91c1c' },
      seedX: 20,
      seedY: 20,
    })
    expect(solid?.style).toEqual({ kind: 'solid', color: '#B91C1C' })

    const gradient = parseFillOp({
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
    expect(gradient?.style.kind).toBe('gradient')

    const fabric = parseFillOp({
      contour: [0, 0, 20, 0, 20, 20, 0, 20],
      style: { kind: 'fabric', fabricId: 'denim' },
      seedX: 5,
      seedY: 5,
    })
    expect(fabric?.style).toEqual({ kind: 'fabric', fabricId: 'denim' })
  })

  it('rejects unknown fabrics and tiny contours', () => {
    expect(
      parseFillOp({
        contour: [0, 0, 1, 1],
        style: { kind: 'solid', color: '#111111' },
      }),
    ).toBeNull()
    expect(
      parseFillOp({
        contour: [0, 0, 20, 0, 20, 20, 0, 20],
        style: { kind: 'fabric', fabricId: 'velvet-unknown' },
      }),
    ).toBeNull()
  })

  it('clones fills without sharing contour arrays', () => {
    const original = [
      {
        id: 'a',
        contour: [1, 2, 3, 4, 5, 6],
        style: solidStyle('#111111'),
        seedX: 2,
        seedY: 3,
      },
    ]
    const cloned = cloneFills(original)
    cloned[0]!.contour[0] = 99
    expect(original[0]!.contour[0]).toBe(1)
  })

  it('exposes fashion fabric and gradient presets', () => {
    expect(FABRIC_PRESETS.map((f) => f.id)).toEqual([
      'satin',
      'denim',
      'cotton',
      'lace',
      'floral',
      'sequins',
    ])
    expect(fabricStyle('lace')?.fabricId).toBe('lace')
    expect(gradientStyleFromPreset('champagne')?.colors[0]).toBe('#F8F4F0')
    expect(contourToSvgPath([0, 0, 10, 0, 10, 10])).toMatch(/^M 0 0 L 10 0 L 10 10 Z$/)
  })
})
