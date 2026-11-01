/**
 * WEB-V4G: closed-region custom gradient fill — offline/deterministic.
 * No paid Magic. Uses the same closed-rect barrier fixture as floodFill.test.ts
 * (jsdom cannot reliably rasterize freehand ink for floodFillRegion).
 */
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { floodFillAgainstBarrier } from '@/lib/floodFill'
import {
  CUSTOM_GRADIENT_ID,
  customGradientStyle,
  gradientPreviewCss,
  parseFillOp,
  type FillOp,
} from '@/lib/fills'
import { paintFillOps } from '@/lib/paintFills'
import { createEmptyDraftDocument, parseStudioDraftDocument } from '@/lib/draftDocument'
import { captureSketchForMagic } from '@/lib/sketchCapture'
import { exportSketchPng } from '@/lib/exportCanvas'
import { type Stroke } from '@/lib/strokes'
import { PAPER_HEIGHT, PAPER_WIDTH, designToPaperIndex } from '@/lib/paperBounds'

vi.mock('@/lib/exportCanvas', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/exportCanvas')>()
  return {
    ...actual,
    exportSketchPng: vi.fn(),
  }
})

const exportMock = vi.mocked(exportSketchPng)

beforeAll(() => {
  if (typeof Path2D === 'undefined') {
    // @ts-expect-error test polyfill
    globalThis.Path2D = class Path2D {
      constructor(_path?: string) {}
    }
  }
})

beforeEach(() => {
  exportMock.mockReset()
})

/** Closed rectangle ring so the interior is fillable and does not touch the paper edge. */
function closedRectBarrier(x0: number, y0: number, x1: number, y1: number): Uint8Array {
  const barrier = new Uint8Array(PAPER_WIDTH * PAPER_HEIGHT)
  const mark = (x: number, y: number) => {
    const i = designToPaperIndex(x, y)
    if (i >= 0) barrier[i] = 1
  }
  for (let x = x0; x <= x1; x += 1) {
    mark(x, y0)
    mark(x, y1)
  }
  for (let y = y0; y <= y1; y += 1) {
    mark(x0, y)
    mark(x1, y)
  }
  return barrier
}

function mockPaintCtx() {
  const gradientStops: Array<[number, string]> = []
  const createCalls: Array<[number, number, number, number]> = []
  const gradient = {
    addColorStop: (offset: number, color: string) => {
      gradientStops.push([offset, color])
    },
  }
  const ctx = {
    fillStyle: '#000' as string | CanvasGradient | CanvasPattern,
    globalAlpha: 1,
    fill: vi.fn(),
    createLinearGradient: vi.fn((x0: number, y0: number, x1: number, y1: number) => {
      createCalls.push([x0, y0, x1, y1])
      return gradient as unknown as CanvasGradient
    }),
    createPattern: vi.fn(),
    save: vi.fn(),
    restore: vi.fn(),
  }
  return { ctx, gradientStops, createCalls }
}

describe('custom gradient closed-region fill (WEB-V4G)', () => {
  it.each([
    { angle: 0, label: 'horizontal' },
    { angle: 90, label: 'vertical' },
    { angle: 45, label: 'diagonal-45' },
    { angle: 135, label: 'diagonal-135' },
  ])('fills a closed outline with custom gradient at $angle° ($label)', ({ angle }) => {
    const style = customGradientStyle(['#FF2D8A', '#0F172A'], angle)
    expect(style).not.toBeNull()
    const barrier = closedRectBarrier(220, 280, 420, 520)
    const result = floodFillAgainstBarrier({
      barrier,
      x: 320,
      y: 400,
      style: style!,
    })
    expect(result.ok).toBe(true)
    if (!result.ok) return
    expect(result.fill.style).toEqual({
      kind: 'gradient',
      gradientId: CUSTOM_GRADIENT_ID,
      colors: ['#FF2D8A', '#0F172A'],
      angle,
    })
    const parsed = parseFillOp(JSON.parse(JSON.stringify(result.fill)))
    expect(parsed).toEqual(result.fill)

    const { ctx, gradientStops, createCalls } = mockPaintCtx()
    paintFillOps(ctx, [result.fill])
    expect(ctx.fill).toHaveBeenCalledTimes(1)
    expect(gradientStops).toEqual([
      [0, '#FF2D8A'],
      [1, '#0F172A'],
    ])
    expect(createCalls.length).toBe(1)
    const [x0, y0, x1, y1] = createCalls[0]!
    const dx = x1 - x0
    const dy = y1 - y0
    const rad = (angle * Math.PI) / 180
    expect(Math.atan2(dy, dx)).toBeCloseTo(Math.atan2(Math.sin(rad), Math.cos(rad)), 5)
    expect(gradientPreviewCss(['#FF2D8A', '#0F172A'], angle)).toContain(
      `${((angle + 90) % 360 + 360) % 360}deg`,
    )
  })

  it('save/reopen draft and local Magic capture retain custom gradient identity', async () => {
    const style = customGradientStyle(['#FF0044', '#0044FF'], 45)!
    const fillResult = floodFillAgainstBarrier({
      barrier: closedRectBarrier(220, 280, 420, 520),
      x: 320,
      y: 400,
      style,
    })
    expect(fillResult.ok).toBe(true)
    if (!fillResult.ok) return
    const fills: FillOp[] = [fillResult.fill]
    const strokes: Stroke[] = [
      {
        id: 'outline',
        tool: 'draw',
        // Freehand stride: [x, y, pressure, ...]
        points: [220, 280, 0.5, 420, 280, 0.5, 420, 520, 0.5, 220, 520, 0.5, 220, 280, 0.5],
        color: '#111111',
        size: 6,
        opacity: 1,
      },
    ]

    const draft = {
      ...createEmptyDraftDocument(),
      strokes,
      fills,
      dimmed: true,
    }
    const reopened = parseStudioDraftDocument(JSON.parse(JSON.stringify(draft)))
    expect(reopened?.fills[0]?.style).toEqual({
      kind: 'gradient',
      gradientId: 'custom',
      colors: ['#FF0044', '#0044FF'],
      angle: 45,
    })

    exportMock.mockResolvedValue({
      blob: new Blob([new Uint8Array([9, 8, 7, 6])], { type: 'image/png' }),
      referenceIncluded: false,
    })
    const captured = await captureSketchForMagic({
      strokes,
      fills,
      referenceUrl: null,
    })
    expect(exportMock).toHaveBeenCalledWith(
      expect.objectContaining({
        fills: expect.arrayContaining([
          expect.objectContaining({
            style: expect.objectContaining({
              gradientId: 'custom',
              colors: ['#FF0044', '#0044FF'],
              angle: 45,
            }),
          }),
        ]),
      }),
    )
    expect(captured.dataUrl.startsWith('data:image/png')).toBe(true)
  })
})
