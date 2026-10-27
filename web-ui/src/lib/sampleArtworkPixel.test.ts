import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { FillOp } from '@/lib/fills'
import type { Stroke } from '@/lib/strokes'
import { DESIGN_HEIGHT, DESIGN_WIDTH } from '@/lib/strokes'

type Buf = Uint8ClampedArray
type Ctx = {
  __buf: Buf
  clearRect: () => void
  scale: () => void
  drawImage: (src: { getContext: () => Ctx }) => void
  getImageData: (x: number, y: number) => { data: Uint8ClampedArray }
}

function setPixel(buf: Buf, x: number, y: number, r: number, g: number, b: number, a = 255) {
  if (x < 0 || y < 0 || x >= DESIGN_WIDTH || y >= DESIGN_HEIGHT) return
  const i = (y * DESIGN_WIDTH + x) * 4
  buf[i] = r
  buf[i + 1] = g
  buf[i + 2] = b
  buf[i + 3] = a
}

function getPixel(buf: Buf, x: number, y: number) {
  const i = (y * DESIGN_WIDTH + x) * 4
  return [buf[i]!, buf[i + 1]!, buf[i + 2]!, buf[i + 3]!] as const
}

function clearBuf(buf: Buf) {
  buf.fill(0)
}

function blendOver(dst: Buf, src: Buf) {
  for (let i = 0; i < dst.length; i += 4) {
    const sa = src[i + 3]! / 255
    if (sa <= 0) continue
    const da = dst[i + 3]! / 255
    const outA = sa + da * (1 - sa)
    if (outA <= 0) {
      dst[i] = dst[i + 1] = dst[i + 2] = dst[i + 3] = 0
      continue
    }
    dst[i] = Math.round((src[i]! * sa + dst[i]! * da * (1 - sa)) / outA)
    dst[i + 1] = Math.round((src[i + 1]! * sa + dst[i + 1]! * da * (1 - sa)) / outA)
    dst[i + 2] = Math.round((src[i + 2]! * sa + dst[i + 2]! * da * (1 - sa)) / outA)
    dst[i + 3] = Math.round(outA * 255)
  }
}

function paintOneFill(buf: Buf, fill: FillOp) {
  if (fill.style.kind === 'solid') {
    const hex = fill.style.color.slice(1)
    const r = parseInt(hex.slice(0, 2), 16)
    const g = parseInt(hex.slice(2, 4), 16)
    const b = parseInt(hex.slice(4, 6), 16)
    for (let y = fill.seedY - 2; y <= fill.seedY + 2; y += 1) {
      for (let x = fill.seedX - 2; x <= fill.seedX + 2; x += 1) {
        setPixel(buf, x, y, r, g, b)
      }
    }
  } else if (fill.style.kind === 'gradient') {
    setPixel(buf, fill.seedX - 20, fill.seedY, 255, 0, 0)
    setPixel(buf, fill.seedX + 20, fill.seedY, 0, 0, 255)
  } else if (fill.style.kind === 'fabric') {
    setPixel(buf, fill.seedX, fill.seedY, 30, 58, 138)
    setPixel(buf, fill.seedX + 1, fill.seedY, 147, 197, 253)
  }
}

function paintFillsWithErasersOnto(buf: Buf, fills: FillOp[], strokes: Stroke[]) {
  for (const fill of fills) {
    paintOneFill(buf, fill)
    const after = fill.eraseAfterStrokeIndex ?? 0
    for (let i = after; i < strokes.length; i += 1) {
      const stroke = strokes[i]!
      if (stroke.tool !== 'erase') continue
      const x = Math.round(stroke.points[0] ?? 0)
      const y = Math.round(stroke.points[1] ?? 0)
      setPixel(buf, x, y, 0, 0, 0, 0)
    }
  }
}

function paintInkOnto(buf: Buf, strokes: Stroke[]) {
  for (const stroke of strokes) {
    const x = Math.round(stroke.points[0] ?? 0)
    const y = Math.round(stroke.points[1] ?? 0)
    if (stroke.tool === 'erase') {
      setPixel(buf, x, y, 0, 0, 0, 0)
      continue
    }
    const hex = stroke.color.slice(1)
    setPixel(
      buf,
      x,
      y,
      parseInt(hex.slice(0, 2), 16),
      parseInt(hex.slice(2, 4), 16),
      parseInt(hex.slice(4, 6), 16),
      Math.round(stroke.opacity * 255),
    )
  }
}

/**
 * Mirrors production compositeFillAndInkLayers: fills and ink are separate buffers;
 * eraser punches both (fills honor eraseAfterStrokeIndex chronology).
 */
vi.mock('@/lib/exportCanvas', () => ({
  compositeFillAndInkLayers: (
    target: Ctx,
    options: { fills: FillOp[]; strokes: Stroke[]; width: number; height: number },
  ) => {
    const fillBuf = new Uint8ClampedArray(options.width * options.height * 4)
    const inkBuf = new Uint8ClampedArray(options.width * options.height * 4)
    paintFillsWithErasersOnto(fillBuf, options.fills, options.strokes)
    paintInkOnto(inkBuf, options.strokes)
    blendOver(target.__buf, fillBuf)
    blendOver(target.__buf, inkBuf)
  },
}))

describe('sampleArtworkPixel', () => {
  beforeEach(() => {
    const realCreate = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation(((tag: string) => {
      if (tag !== 'canvas') return realCreate(tag)
      const buf = new Uint8ClampedArray(DESIGN_WIDTH * DESIGN_HEIGHT * 4)
      const ctx: Ctx = {
        __buf: buf,
        clearRect: () => clearBuf(buf),
        scale: () => undefined,
        drawImage: () => undefined,
        getImageData: (x: number, y: number) => ({
          data: Uint8ClampedArray.from(getPixel(buf, x, y)),
        }),
      }
      return {
        width: DESIGN_WIDTH,
        height: DESIGN_HEIGHT,
        getContext: () => ctx,
      } as unknown as HTMLCanvasElement
    }) as typeof document.createElement)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('samples black ink over a red fill (foreground ink wins)', async () => {
    const { sampleArtworkPixel } = await import('@/lib/sampleArtworkPixel')
    const fills: FillOp[] = [
      {
        id: 'f',
        contour: [10, 10, 40, 10, 40, 40, 10, 40],
        style: { kind: 'solid', color: '#B91C1C' },
        seedX: 20,
        seedY: 20,
      },
    ]
    const strokes: Stroke[] = [
      {
        id: 'ink',
        tool: 'draw',
        points: [20, 20, 0.5],
        color: '#111111',
        size: 4,
        opacity: 1,
      },
    ]
    expect(sampleArtworkPixel({ fills, strokes, x: 20, y: 20 }).hex).toBe('#111111')
    expect(sampleArtworkPixel({ fills, strokes: [], x: 20, y: 20 }).hex).toBe('#B91C1C')
  })

  it('erases fill pixels along with ink at the same point', async () => {
    const { sampleArtworkPixel } = await import('@/lib/sampleArtworkPixel')
    const fills: FillOp[] = [
      {
        id: 'f',
        contour: [10, 10, 40, 10, 40, 40, 10, 40],
        style: { kind: 'solid', color: '#B91C1C' },
        seedX: 20,
        seedY: 20,
        eraseAfterStrokeIndex: 0,
      },
    ]
    const strokes: Stroke[] = [
      {
        id: 'ink',
        tool: 'draw',
        points: [20, 20, 0.5],
        color: '#111111',
        size: 4,
        opacity: 1,
      },
      {
        id: 'erase',
        tool: 'erase',
        points: [20, 20, 0.5],
        color: '#000000',
        size: 8,
        opacity: 1,
      },
    ]
    const sampled = sampleArtworkPixel({ fills, strokes, x: 20, y: 20 })
    expect(sampled.hit).toBe(false)
  })

  it('keeps fill pixels when erase happened before the fill was created', async () => {
    const { sampleArtworkPixel } = await import('@/lib/sampleArtworkPixel')
    const fills: FillOp[] = [
      {
        id: 'f',
        contour: [10, 10, 40, 10, 40, 40, 10, 40],
        style: { kind: 'solid', color: '#B91C1C' },
        seedX: 20,
        seedY: 20,
        eraseAfterStrokeIndex: 2,
      },
    ]
    const strokes: Stroke[] = [
      {
        id: 'ink',
        tool: 'draw',
        points: [20, 20, 0.5],
        color: '#111111',
        size: 4,
        opacity: 1,
      },
      {
        id: 'erase',
        tool: 'erase',
        points: [20, 20, 0.5],
        color: '#000000',
        size: 8,
        opacity: 1,
      },
    ]
    const sampled = sampleArtworkPixel({ fills, strokes, x: 20, y: 20 })
    expect(sampled.hit).toBe(true)
    expect(sampled.hex).toBe('#B91C1C')
  })

  it('erases fabric and gradient fill pixels at the eraser tip', async () => {
    const { sampleArtworkPixel } = await import('@/lib/sampleArtworkPixel')
    const fabric: FillOp[] = [
      {
        id: 'denim',
        contour: [0, 0, 20, 0, 20, 20, 0, 20],
        style: { kind: 'fabric', fabricId: 'denim' },
        seedX: 10,
        seedY: 10,
        eraseAfterStrokeIndex: 0,
      },
    ]
    const gradient: FillOp[] = [
      {
        id: 'g',
        contour: [0, 0, 100, 0, 100, 40, 0, 40],
        style: {
          kind: 'gradient',
          gradientId: 'test',
          colors: ['#FF0000', '#0000FF'],
          angle: 0,
        },
        seedX: 50,
        seedY: 20,
        eraseAfterStrokeIndex: 0,
      },
    ]
    const eraseAt = (x: number, y: number): Stroke[] => [
      {
        id: 'ink',
        tool: 'draw',
        points: [x, y, 0.5],
        color: '#111111',
        size: 4,
        opacity: 1,
      },
      {
        id: 'erase',
        tool: 'erase',
        points: [x, y, 0.5],
        color: '#000000',
        size: 8,
        opacity: 1,
      },
    ]
    expect(sampleArtworkPixel({ fills: fabric, strokes: eraseAt(10, 10), x: 10, y: 10 }).hit).toBe(
      false,
    )
    expect(sampleArtworkPixel({ fills: gradient, strokes: eraseAt(30, 20), x: 30, y: 20 }).hit).toBe(
      false,
    )
  })

  it('samples distinct gradient positions', async () => {
    const { sampleArtworkPixel } = await import('@/lib/sampleArtworkPixel')
    const fills: FillOp[] = [
      {
        id: 'g',
        contour: [0, 0, 100, 0, 100, 40, 0, 40],
        style: {
          kind: 'gradient',
          gradientId: 'test',
          colors: ['#FF0000', '#0000FF'],
          angle: 0,
        },
        seedX: 50,
        seedY: 20,
      },
    ]
    const left = sampleArtworkPixel({ fills, strokes: [], x: 30, y: 20 })
    const right = sampleArtworkPixel({ fills, strokes: [], x: 70, y: 20 })
    expect(left.hex).toBe('#FF0000')
    expect(right.hex).toBe('#0000FF')
  })

  it('samples fabric texture pixels at the click', async () => {
    const { sampleArtworkPixel } = await import('@/lib/sampleArtworkPixel')
    const fills: FillOp[] = [
      {
        id: 'denim',
        contour: [0, 0, 20, 0, 20, 20, 0, 20],
        style: { kind: 'fabric', fabricId: 'denim' },
        seedX: 10,
        seedY: 10,
      },
    ]
    expect(sampleArtworkPixel({ fills, strokes: [], x: 10, y: 10 }).hex).toBe('#1E3A8A')
    expect(sampleArtworkPixel({ fills, strokes: [], x: 11, y: 10 }).hex).toBe('#93C5FD')
  })

  it('misses empty paper so callers can fall back without inventing a model color', async () => {
    const { sampleArtworkPixel } = await import('@/lib/sampleArtworkPixel')
    const miss = sampleArtworkPixel({ fills: [], strokes: [], x: 5, y: 5 })
    expect(miss.hit).toBe(false)
    expect(DESIGN_HEIGHT).toBeGreaterThan(0)
  })
})
