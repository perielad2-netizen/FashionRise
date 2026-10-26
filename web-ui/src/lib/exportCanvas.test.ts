import { beforeAll, describe, expect, it, vi } from 'vitest'
import {
  compositeFillAndInkLayers,
  paintFillsWithErasers,
  paintInkStrokes,
} from '@/lib/exportCanvas'
import type { FillOp } from '@/lib/fills'
import type { Stroke } from '@/lib/strokes'

vi.mock('@/lib/freehand', () => ({
  strokeToSvgPath: () => 'M0 0 L10 10 Z',
}))

beforeAll(() => {
  // jsdom lacks Path2D; export only needs construction for fill().
  if (typeof Path2D === 'undefined') {
    // @ts-expect-error test polyfill
    globalThis.Path2D = class Path2D {
      constructor(_path?: string) {}
    }
  }
})

function mockCtx() {
  const ops: string[] = []
  const ctx = {
    fillStyle: '#000',
    globalAlpha: 1,
    globalCompositeOperation: 'source-over' as string,
    fillRect: vi.fn(),
    fill: vi.fn(() => {
      ops.push(`fill:${ctx.globalCompositeOperation}`)
    }),
    drawImage: vi.fn(),
    save: vi.fn(),
    restore: vi.fn(),
  }
  return { ctx, ops }
}

describe('paintInkStrokes (ink-only eraser)', () => {
  it('uses destination-out only for erase strokes on the ink layer', () => {
    const { ctx, ops } = mockCtx()
    const strokes: Stroke[] = [
      {
        id: 'd1',
        tool: 'draw',
        points: [0, 0, 0.5, 10, 10, 0.5],
        color: '#111',
        size: 4,
        opacity: 1,
      },
      {
        id: 'e1',
        tool: 'erase',
        points: [2, 2, 0.5, 8, 8, 0.5],
        color: '#000',
        size: 8,
        opacity: 1,
      },
    ]

    paintInkStrokes(ctx, strokes)

    expect(ops).toEqual(['fill:source-over', 'fill:destination-out'])
    // Eraser never draws onto a shared base — callers must composite ink over base separately.
    expect(ctx.drawImage).not.toHaveBeenCalled()
  })
})

describe('paintFillsWithErasers', () => {
  it('applies destination-out erase strokes to the fill layer after each fill', () => {
    const { ctx, ops } = mockCtx()
    const fills: FillOp[] = [
      {
        id: 'f',
        contour: [0, 0, 10, 0, 10, 10, 0, 10],
        style: { kind: 'solid', color: '#BE185D' },
        seedX: 5,
        seedY: 5,
        eraseAfterStrokeIndex: 0,
      },
    ]
    const strokes: Stroke[] = [
      {
        id: 'e1',
        tool: 'erase',
        points: [2, 2, 0.5, 8, 8, 0.5],
        color: '#000',
        size: 8,
        opacity: 1,
      },
    ]
    paintFillsWithErasers(ctx, fills, strokes)
    expect(ops).toContain('fill:destination-out')
    expect(ops[0]).toBe('fill:source-over')
  })

  it('skips erasers that occurred before the fill was created', () => {
    const { ctx, ops } = mockCtx()
    const fills: FillOp[] = [
      {
        id: 'f',
        contour: [0, 0, 10, 0, 10, 10, 0, 10],
        style: { kind: 'solid', color: '#BE185D' },
        seedX: 5,
        seedY: 5,
        eraseAfterStrokeIndex: 1,
      },
    ]
    const strokes: Stroke[] = [
      {
        id: 'e-old',
        tool: 'erase',
        points: [2, 2, 0.5, 8, 8, 0.5],
        color: '#000',
        size: 8,
        opacity: 1,
      },
    ]
    paintFillsWithErasers(ctx, fills, strokes)
    expect(ops).toEqual(['fill:source-over'])
    expect(ops).not.toContain('fill:destination-out')
  })
})

describe('compositeFillAndInkLayers', () => {
  it('draws fill and ink from separate canvases onto the target', () => {
    const created: unknown[] = []
    const realCreate = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation(((tag: string) => {
      if (tag !== 'canvas') return realCreate(tag)
      const canvas = {
        width: 0,
        height: 0,
        getContext: () => ({
          scale: vi.fn(),
          fillStyle: '#000',
          globalAlpha: 1,
          globalCompositeOperation: 'source-over',
          save: vi.fn(),
          restore: vi.fn(),
          fill: vi.fn(),
          fillRect: vi.fn(),
          beginPath: vi.fn(),
          moveTo: vi.fn(),
          lineTo: vi.fn(),
          closePath: vi.fn(),
          createLinearGradient: () => ({ addColorStop: vi.fn() }),
          createPattern: () => null,
          drawImage: vi.fn(),
          setLineDash: vi.fn(),
          clip: vi.fn(),
        }),
      }
      created.push(canvas)
      return canvas as unknown as HTMLCanvasElement
    }) as typeof document.createElement)

    const drawImage = vi.fn()
    const target = {
      fillStyle: '#000',
      globalAlpha: 1,
      globalCompositeOperation: 'source-over',
      fillRect: vi.fn(),
      fill: vi.fn(),
      drawImage,
      save: vi.fn(),
      restore: vi.fn(),
    }

    const fills: FillOp[] = [
      {
        id: 'f',
        contour: [0, 0, 10, 0, 10, 10, 0, 10],
        style: { kind: 'solid', color: '#B91C1C' },
        seedX: 5,
        seedY: 5,
      },
    ]
    const strokes: Stroke[] = [
      {
        id: 'd',
        tool: 'draw',
        points: [0, 0, 0.5, 10, 10, 0.5],
        color: '#111111',
        size: 4,
        opacity: 1,
      },
    ]

    compositeFillAndInkLayers(target, {
      fills,
      strokes,
      width: 32,
      height: 32,
    })

    expect(created).toHaveLength(2)
    expect(drawImage).toHaveBeenCalledTimes(2)
    expect(drawImage.mock.calls[0]![0]).toBe(created[0])
    expect(drawImage.mock.calls[1]![0]).toBe(created[1])
    vi.restoreAllMocks()
  })
})
