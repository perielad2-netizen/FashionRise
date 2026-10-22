import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { FillOp } from '@/lib/fills'
import type { Stroke } from '@/lib/strokes'
import { DESIGN_HEIGHT, DESIGN_WIDTH } from '@/lib/strokes'

const pixels = new Uint8ClampedArray(DESIGN_WIDTH * DESIGN_HEIGHT * 4)

function setPixel(x: number, y: number, r: number, g: number, b: number, a = 255) {
  const i = (y * DESIGN_WIDTH + x) * 4
  pixels[i] = r
  pixels[i + 1] = g
  pixels[i + 2] = b
  pixels[i + 3] = a
}

function clearPixels() {
  pixels.fill(0)
}

vi.mock('@/lib/paintFills', () => ({
  paintFillOps: (_ctx: unknown, fills: FillOp[]) => {
    for (const fill of fills) {
      if (fill.style.kind === 'solid') {
        const hex = fill.style.color.slice(1)
        const r = parseInt(hex.slice(0, 2), 16)
        const g = parseInt(hex.slice(2, 4), 16)
        const b = parseInt(hex.slice(4, 6), 16)
        // Fill a small patch around the seed.
        for (let y = fill.seedY - 2; y <= fill.seedY + 2; y += 1) {
          for (let x = fill.seedX - 2; x <= fill.seedX + 2; x += 1) {
            setPixel(x, y, r, g, b)
          }
        }
      } else if (fill.style.kind === 'gradient') {
        // Distinct left/right colors along X inside the contour bounds.
        setPixel(fill.seedX - 20, fill.seedY, 255, 0, 0)
        setPixel(fill.seedX + 20, fill.seedY, 0, 0, 255)
      } else if (fill.style.kind === 'fabric') {
        // Texture-like non-uniform pixels.
        setPixel(fill.seedX, fill.seedY, 30, 58, 138) // denim-ish
        setPixel(fill.seedX + 1, fill.seedY, 147, 197, 253)
      }
    }
  },
}))

vi.mock('@/lib/exportCanvas', () => ({
  paintInkStrokes: (_ctx: unknown, strokes: Stroke[]) => {
    for (const stroke of strokes) {
      if (stroke.tool === 'erase') {
        const x = Math.round(stroke.points[0] ?? 0)
        const y = Math.round(stroke.points[1] ?? 0)
        setPixel(x, y, 0, 0, 0, 0)
        continue
      }
      const x = Math.round(stroke.points[0] ?? 0)
      const y = Math.round(stroke.points[1] ?? 0)
      const hex = stroke.color.slice(1)
      setPixel(
        x,
        y,
        parseInt(hex.slice(0, 2), 16),
        parseInt(hex.slice(2, 4), 16),
        parseInt(hex.slice(4, 6), 16),
        Math.round(stroke.opacity * 255),
      )
    }
  },
}))

describe('sampleArtworkPixel', () => {
  beforeEach(() => {
    clearPixels()
    const realCreate = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation(((tag: string) => {
      if (tag !== 'canvas') return realCreate(tag)
      return {
        width: DESIGN_WIDTH,
        height: DESIGN_HEIGHT,
        getContext: () => ({
          clearRect: () => clearPixels(),
          getImageData: (x: number, y: number) => ({
            data: pixels.slice((y * DESIGN_WIDTH + x) * 4, (y * DESIGN_WIDTH + x) * 4 + 4),
          }),
        }),
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
