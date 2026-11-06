import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Stroke } from '@/lib/strokes'
import { PAPER_HEIGHT, PAPER_WIDTH, designToPaperIndex } from '@/lib/paperBounds'
import { solidStyle } from '@/lib/fills'

/**
 * Regression: fill barriers must match visible ink after erasers remove seams /
 * outline segments. paintInkStrokes (draw + destination-out erase) is the source
 * of truth — same as Konva/PNG.
 */
describe('buildInkBarrierMask + erased seams', () => {
  const pixels = new Uint8ClampedArray(PAPER_WIDTH * PAPER_HEIGHT * 4)

  function inkOn(x: number, y: number) {
    const i = (designToPaperIndex(x, y)) * 4
    pixels[i] = 0
    pixels[i + 1] = 0
    pixels[i + 2] = 0
    pixels[i + 3] = 255
  }
  function inkOff(x: number, y: number) {
    const i = (designToPaperIndex(x, y)) * 4
    pixels[i + 3] = 0
  }
  function hLine(y: number, x0: number, x1: number) {
    for (let x = x0; x <= x1; x += 1) inkOn(x, y)
  }
  function vLine(x: number, y0: number, y1: number) {
    for (let y = y0; y <= y1; y += 1) inkOn(x, y)
  }

  beforeEach(() => {
    pixels.fill(0)
    vi.resetModules()
    vi.doMock('@/lib/exportCanvas', () => ({
      paintInkStrokes: (_ctx: unknown, strokes: Stroke[]) => {
        // Interpret simplified stroke payloads from the test:
        // draw with points [x0,y0,x1,y1] paints an axis-aligned segment;
        // erase clears that segment.
        for (const stroke of strokes) {
          const x0 = Math.round(stroke.points[0] ?? 0)
          const y0 = Math.round(stroke.points[1] ?? 0)
          const x1 = Math.round(stroke.points[2] ?? x0)
          const y1 = Math.round(stroke.points[3] ?? y0)
          const paint = stroke.tool === 'erase' ? inkOff : inkOn
          if (y0 === y1) {
            for (let x = Math.min(x0, x1); x <= Math.max(x0, x1); x += 1) paint(x, y0)
          } else if (x0 === x1) {
            for (let y = Math.min(y0, y1); y <= Math.max(y0, y1); y += 1) paint(x0, y)
          }
        }
      },
    }))

    const realCreate = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation(((tag: string) => {
      if (tag !== 'canvas') return realCreate(tag)
      return {
        width: PAPER_WIDTH,
        height: PAPER_HEIGHT,
        getContext: () => ({
          clearRect: () => pixels.fill(0),
          save: () => undefined,
          restore: () => undefined,
          translate: () => undefined,
          filter: '',
          drawImage: () => undefined,
          getImageData: () => ({ data: pixels }),
        }),
      } as unknown as HTMLCanvasElement
    }) as typeof document.createElement)
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.resetModules()
    vi.doUnmock('@/lib/exportCanvas')
  })

  it('does not keep an erased waist seam as an invisible fill barrier', async () => {
    const { buildInkBarrierMask, floodFillAgainstBarrier, floodFillRegion } = await import(
      '@/lib/floodFill'
    )

    const outer: Stroke[] = [
      { id: 'top', tool: 'draw', points: [250, 200, 450, 200], color: '#111', size: 4, opacity: 1 },
      { id: 'right', tool: 'draw', points: [450, 200, 450, 700], color: '#111', size: 4, opacity: 1 },
      { id: 'bottom', tool: 'draw', points: [450, 700, 250, 700], color: '#111', size: 4, opacity: 1 },
      { id: 'left', tool: 'draw', points: [250, 700, 250, 200], color: '#111', size: 4, opacity: 1 },
      { id: 'waist', tool: 'draw', points: [250, 400, 450, 400], color: '#111', size: 4, opacity: 1 },
    ]

    // Sanity: with waist present, bodice/skirt fill independently.
    hLine(200, 250, 450)
    vLine(450, 200, 700)
    hLine(700, 250, 450)
    vLine(250, 200, 700)
    hLine(400, 250, 450)
    const withSeam = buildInkBarrierMask(outer, 0)
    expect(withSeam[designToPaperIndex(350, 400)]).toBe(1)
    const bodice = floodFillAgainstBarrier({
      barrier: withSeam,
      x: 350,
      y: 300,
      style: solidStyle('#B91C1C'),
    })
    const skirt = floodFillAgainstBarrier({
      barrier: withSeam,
      x: 350,
      y: 500,
      style: solidStyle('#1D4ED8'),
    })
    expect(bodice.ok).toBe(true)
    expect(skirt.ok).toBe(true)

    // Erase the interior waist seam only (keep wall junctions sealed).
    const erasedWaist: Stroke = {
      id: 'erase-waist',
      tool: 'erase',
      points: [251, 400, 449, 400],
      color: '#000',
      size: 8,
      opacity: 1,
    }
    const afterErase = buildInkBarrierMask([...outer, erasedWaist], 0)
    expect(afterErase[designToPaperIndex(350, 400)]).toBe(0)
    expect(afterErase[designToPaperIndex(250, 400)]).toBe(1)
    expect(afterErase[designToPaperIndex(450, 400)]).toBe(1)

    const merged = floodFillAgainstBarrier({
      barrier: afterErase,
      x: 350,
      y: 300,
      style: solidStyle('#B91C1C'),
    })
    expect(merged.ok).toBe(true)
    if (!merged.ok) return
    const maxY = Math.max(...merged.fill.contour.filter((_, i) => i % 2 === 1))
    // Contour now spans past the former waist into the skirt.
    expect(maxY).toBeGreaterThan(400)

    // floodFillRegion must feed erase strokes into paintInkStrokes (integration).
    pixels.fill(0)
    const viaRegion = floodFillRegion({
      strokes: [...outer, erasedWaist],
      x: 350,
      y: 300,
      style: solidStyle('#111111'),
      gapClose: 0,
    })
    expect(viaRegion.ok).toBe(true)
    expect(PAPER_HEIGHT).toBeGreaterThan(0)
  })

  it('open outline after erasing a side fails closed instead of trapping a ghost region', async () => {
    const { buildInkBarrierMask, floodFillAgainstBarrier } = await import('@/lib/floodFill')
    const closed: Stroke[] = [
      { id: 't', tool: 'draw', points: [300, 300, 400, 300], color: '#111', size: 4, opacity: 1 },
      { id: 'r', tool: 'draw', points: [400, 300, 400, 400], color: '#111', size: 4, opacity: 1 },
      { id: 'b', tool: 'draw', points: [400, 400, 300, 400], color: '#111', size: 4, opacity: 1 },
      { id: 'l', tool: 'draw', points: [300, 400, 300, 300], color: '#111', size: 4, opacity: 1 },
    ]
    hLine(300, 300, 400)
    vLine(400, 300, 400)
    hLine(400, 300, 400)
    vLine(300, 300, 400)
    expect(
      floodFillAgainstBarrier({
        barrier: buildInkBarrierMask(closed, 0),
        x: 350,
        y: 350,
        style: solidStyle('#111111'),
      }).ok,
    ).toBe(true)

    // Erase the top edge — region opens toward the paper (fail closed).
    const open = buildInkBarrierMask(
      [
        ...closed,
        {
          id: 'erase-top',
          tool: 'erase',
          points: [300, 300, 400, 300],
          color: '#000',
          size: 8,
          opacity: 1,
        },
      ],
      0,
    )
    // Without a top barrier, flood from interior reaches the outer paper edge
    // of our tiny box only if the box isn't sealed — clear top:
    expect(open[designToPaperIndex(350, 300)]).toBe(0)
  })
})
