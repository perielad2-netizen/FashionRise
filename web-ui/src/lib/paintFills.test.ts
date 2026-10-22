import { beforeAll, describe, expect, it, vi } from 'vitest'
import { paintFillOps, sampleColorFromStyle } from '@/lib/paintFills'
import type { FillOp } from '@/lib/fills'

beforeAll(() => {
  if (typeof Path2D === 'undefined') {
    // @ts-expect-error test polyfill
    globalThis.Path2D = class Path2D {
      constructor(_path?: string) {}
    }
  }
})

function mockCtx() {
  const fills: Array<string | CanvasGradient | CanvasPattern> = []
  const gradientStops: Array<[number, string]> = []
  const gradient = {
    addColorStop: (offset: number, color: string) => {
      gradientStops.push([offset, color])
    },
  }
  const pattern = { id: 'pattern' }
  const ctx = {
    fillStyle: '#000' as string | CanvasGradient | CanvasPattern,
    globalAlpha: 1,
    fill: vi.fn(() => {
      fills.push(ctx.fillStyle)
    }),
    createLinearGradient: vi.fn(() => gradient as unknown as CanvasGradient),
    createPattern: vi.fn(() => pattern as unknown as CanvasPattern),
    save: vi.fn(),
    restore: vi.fn(),
  }
  return { ctx, fills, gradientStops }
}

describe('paintFillOps', () => {
  it('paints solid, gradient and fabric fills in order', () => {
    const { ctx, fills, gradientStops } = mockCtx()
    const ops: FillOp[] = [
      {
        id: 's',
        contour: [10, 10, 40, 10, 40, 40, 10, 40],
        style: { kind: 'solid', color: '#B91C1C' },
        seedX: 20,
        seedY: 20,
      },
      {
        id: 'g',
        contour: [50, 50, 90, 50, 90, 90, 50, 90],
        style: {
          kind: 'gradient',
          gradientId: 'rose-violet',
          colors: ['#D63384', '#7C3AED'],
          angle: 135,
        },
        seedX: 60,
        seedY: 60,
      },
      {
        id: 'f',
        contour: [100, 100, 140, 100, 140, 140, 100, 140],
        style: { kind: 'fabric', fabricId: 'denim' },
        seedX: 110,
        seedY: 110,
      },
    ]
    paintFillOps(ctx, ops)
    expect(ctx.fill).toHaveBeenCalledTimes(3)
    expect(fills[0]).toBe('#B91C1C')
    expect(ctx.createLinearGradient).toHaveBeenCalled()
    expect(gradientStops).toEqual([
      [0, '#D63384'],
      [1, '#7C3AED'],
    ])
    expect(ctx.createPattern).toHaveBeenCalled()
  })

  it('samples representative colors for eyedropper', () => {
    expect(sampleColorFromStyle({ kind: 'solid', color: '#112233' })).toBe('#112233')
    expect(
      sampleColorFromStyle({
        kind: 'gradient',
        gradientId: 'x',
        colors: ['#AAAAAA', '#BBBBBB'],
        angle: 90,
      }),
    ).toBe('#AAAAAA')
    expect(sampleColorFromStyle({ kind: 'fabric', fabricId: 'denim' })).toBe('#1E3A8A')
  })
})
