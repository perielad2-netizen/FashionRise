import { beforeAll, describe, expect, it, vi } from 'vitest'
import {
  paintFillOps,
  renderUploadedFabricTile,
  sampleColorFromStyle,
  UPLOADED_FABRIC_BASE_TILE_PX,
  UPLOADED_FABRIC_TILE_MAX_PX,
  UPLOADED_FABRIC_TILE_MIN_PX,
} from '@/lib/paintFills'
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

  it('uploaded fabric tile sizes differ at 0.25×, 1×, and 4× even for 2048px sources', () => {
    const img = { width: 2048, height: 2048 } as HTMLImageElement
    const small = renderUploadedFabricTile(img, 0.25)
    const mid = renderUploadedFabricTile(img, 1)
    const large = renderUploadedFabricTile(img, 4)

    expect(small.width).toBe(Math.round(UPLOADED_FABRIC_BASE_TILE_PX * 0.25))
    expect(mid.width).toBe(UPLOADED_FABRIC_BASE_TILE_PX)
    expect(large.width).toBe(
      Math.min(UPLOADED_FABRIC_TILE_MAX_PX, Math.round(UPLOADED_FABRIC_BASE_TILE_PX * 4)),
    )
    expect(small.width).toBeLessThan(mid.width)
    expect(mid.width).toBeLessThan(large.width)
    expect(large.width).toBeLessThanOrEqual(UPLOADED_FABRIC_TILE_MAX_PX)
    expect(small.width).toBeGreaterThanOrEqual(UPLOADED_FABRIC_TILE_MIN_PX)

    // Deterministic: same inputs → same tile size.
    expect(renderUploadedFabricTile(img, 1).width).toBe(mid.width)
    expect(renderUploadedFabricTile(img, 1).height).toBe(mid.height)
  })

  it('uploaded fabric tile scale stays distinct for smaller source images', () => {
    const img = { width: 96, height: 64 } as HTMLImageElement
    const a = renderUploadedFabricTile(img, 0.25)
    const b = renderUploadedFabricTile(img, 1)
    const c = renderUploadedFabricTile(img, 4)
    expect(a.width).toBeLessThan(b.width)
    expect(b.width).toBeLessThan(c.width)
  })
})
