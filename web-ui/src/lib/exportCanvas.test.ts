import { beforeAll, describe, expect, it, vi } from 'vitest'
import { paintInkStrokes } from '@/lib/exportCanvas'
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
