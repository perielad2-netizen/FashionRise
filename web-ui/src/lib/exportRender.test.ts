import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import {
  canvasToPngBlob,
  downloadBlob,
  exportCompositePng,
  exportFilename,
  exportSketchPng,
  renderSketchCanvas,
  withMinimumSize,
} from '@/lib/exportCanvas'
import type { Stroke } from '@/lib/strokes'

const { strokeToSvgPath } = vi.hoisted(() => ({
  strokeToSvgPath: vi.fn((s: Stroke) => `M${s.points[0]} ${s.points[1]} Z`),
}))
vi.mock('@/lib/freehand', () => ({ strokeToSvgPath }))

beforeAll(() => {
  if (typeof Path2D === 'undefined') {
    // @ts-expect-error test polyfill
    globalThis.Path2D = class Path2D {
      constructor(_path?: string) {}
    }
  }
})

type Op = { canvas: number; op: string; detail?: unknown }

function installFakeCanvas(options: { noContext?: boolean; blob?: Blob | null } = {}) {
  const ops: Op[] = []
  let count = 0
  const realCreate = document.createElement.bind(document)
  const spy = vi.spyOn(document, 'createElement').mockImplementation(((tag: string) => {
    if (tag !== 'canvas') return realCreate(tag)
    const index = count++
    const ctx = {
      fillStyle: '' as unknown,
      globalAlpha: 1,
      globalCompositeOperation: 'source-over',
      fillRect: (...a: number[]) => ops.push({ canvas: index, op: 'fillRect', detail: { a, fill: ctx.fillStyle } }),
      fill: () =>
        ops.push({
          canvas: index,
          op: 'fill',
          detail: { mode: ctx.globalCompositeOperation, alpha: ctx.globalAlpha, fill: ctx.fillStyle },
        }),
      drawImage: (img: unknown, ...a: number[]) =>
        ops.push({ canvas: index, op: 'drawImage', detail: { img, a, alpha: ctx.globalAlpha } }),
      save: () => undefined,
      restore: () => {
        ctx.globalAlpha = 1
        ctx.globalCompositeOperation = 'source-over'
      },
      scale: (x: number, y: number) => ops.push({ canvas: index, op: 'scale', detail: [x, y] }),
    }
    const canvas = {
      width: 0,
      height: 0,
      id: `canvas-${index}`,
      getContext: () => (options.noContext ? null : ctx),
      toBlob: (cb: (b: Blob | null) => void) =>
        cb(options.blob === undefined ? new Blob([new Uint8Array([137, 80, 78, 71])], { type: 'image/png' }) : options.blob),
    }
    return canvas as unknown as HTMLCanvasElement
  }) as typeof document.createElement)
  return { ops, spy }
}

const strokes: Stroke[] = [
  { id: 'd', tool: 'draw', points: [100, 100, 0.5], color: '#D63384', size: 3.5, opacity: 0.5 },
  { id: 'e', tool: 'erase', points: [110, 110, 0.5], color: '#000000', size: 7, opacity: 1 },
]

const reference = { width: 384, height: 1024 } as unknown as HTMLImageElement

afterEach(() => {
  vi.restoreAllMocks()
})

describe('renderSketchCanvas composition', () => {
  it('paints cream paper, dimmed reference, then an ink layer composited on top', async () => {
    const { ops } = installFakeCanvas()
    const result = await renderSketchCanvas({
      strokes,
      referenceUrl: '/models/female_model.png',
      referenceOpacity: 0.4,
      loadReference: async () => reference,
    })
    expect(result.referenceIncluded).toBe(true)
    const base = ops.filter((o) => o.canvas === 0)
    const ink = ops.filter((o) => o.canvas === 1)
    expect(base[0]).toMatchObject({ op: 'fillRect', detail: { a: [0, 0, 768, 1024], fill: '#F8F4F0' } })
    expect(base[1]).toMatchObject({ op: 'drawImage', detail: { img: reference, alpha: 0.4, a: [192, 0, 384, 1024] } })
    // Eraser runs on the ink canvas only; the base never receives destination-out.
    expect(ink.map((o) => (o.detail as { mode: string }).mode)).toEqual(['source-over', 'destination-out'])
    expect(ink[0]).toMatchObject({ detail: { alpha: 0.5, fill: '#D63384' } })
    expect(base.some((o) => o.op === 'fill')).toBe(false)
    expect(base[2]).toMatchObject({ op: 'drawImage', detail: { a: [0, 0, 768, 1024] } })
    expect(((base[2]!.detail as { img: { id: string } }).img).id).toBe('canvas-1')
  })

  it('scales design-space strokes and reference to a smaller output', async () => {
    const { ops } = installFakeCanvas()
    await renderSketchCanvas({
      strokes,
      referenceUrl: '/ref.png',
      width: 240,
      height: 320,
      loadReference: async () => reference,
    })
    expect(ops.find((o) => o.op === 'scale')).toMatchObject({ canvas: 1, detail: [0.3125, 0.3125] })
    expect(ops.find((o) => o.canvas === 0 && o.op === 'drawImage')).toMatchObject({ detail: { a: [60, 0, 120, 320] } })
  })

  it('keeps exact stroke sizes unless a minimum output ink size is requested', async () => {
    installFakeCanvas()
    strokeToSvgPath.mockClear()
    await renderSketchCanvas({ strokes, referenceUrl: null, width: 240, height: 320 })
    expect(strokeToSvgPath.mock.calls.map(([s]) => s.size)).toEqual([3.5, 7])

    strokeToSvgPath.mockClear()
    await renderSketchCanvas({ strokes, referenceUrl: null, width: 240, height: 320, minInkSize: 1.5 })
    // 1.5 output px at 0.3125 scale = 4.8 design units; the 7-unit eraser is already larger.
    expect(strokeToSvgPath.mock.calls.map(([s]) => s.size)).toEqual([4.8, 7])
    expect(strokes[0]!.size).toBe(3.5)
  })

  it('withMinimumSize copies only the strokes it widens', () => {
    const out = withMinimumSize(strokes, 5)
    expect(out.map((s) => s.size)).toEqual([5, 7])
    expect(out[0]).not.toBe(strokes[0])
    expect(out[1]).toBe(strokes[1])
  })

  it('skips an unloadable reference and still renders the ink', async () => {
    const { ops } = installFakeCanvas()
    const result = await renderSketchCanvas({
      strokes,
      referenceUrl: 'blob:revoked',
      onReferenceError: 'skip',
      loadReference: async () => {
        throw new Error('Failed to load reference image')
      },
    })
    expect(result.referenceIncluded).toBe(false)
    expect(ops.filter((o) => o.canvas === 1 && o.op === 'fill')).toHaveLength(2)
  })

  it('throws on reference failure when asked to', async () => {
    installFakeCanvas()
    await expect(
      renderSketchCanvas({
        strokes,
        referenceUrl: 'x',
        onReferenceError: 'throw',
        loadReference: async () => {
          throw new Error('Failed to load reference image')
        },
      }),
    ).rejects.toThrow(/reference/)
  })

  it('reports a missing 2D context', async () => {
    installFakeCanvas({ noContext: true })
    await expect(renderSketchCanvas({ strokes, referenceUrl: null })).rejects.toThrow(/Canvas 2D/)
  })
})

describe('PNG output', () => {
  it('exportSketchPng returns an image/png blob and whether the reference made it', async () => {
    installFakeCanvas()
    const result = await exportSketchPng({
      strokes,
      referenceUrl: 'x',
      loadReference: async () => {
        throw new Error('nope')
      },
    })
    expect(result.blob.type).toBe('image/png')
    expect(result.referenceIncluded).toBe(false)
  })

  it('exportCompositePng keeps strict behaviour', async () => {
    installFakeCanvas()
    await expect(exportCompositePng({ strokes, referenceUrl: null })).resolves.toBeInstanceOf(Blob)
  })

  it('rejects an empty or non-PNG encoder result', async () => {
    const canvas = { toBlob: (cb: (b: Blob | null) => void) => cb(null) } as unknown as HTMLCanvasElement
    await expect(canvasToPngBlob(canvas)).rejects.toThrow(/PNG export failed/)
    const jpeg = {
      toBlob: (cb: (b: Blob | null) => void) => cb(new Blob(['x'], { type: 'image/jpeg' })),
    } as unknown as HTMLCanvasElement
    await expect(canvasToPngBlob(jpeg)).rejects.toThrow(/PNG export failed/)
  })
})

describe('download and filename', () => {
  it('clicks a download link and always revokes the object URL', () => {
    const revoke = vi.fn()
    const scheduled: Array<() => void> = []
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    downloadBlob(new Blob(['x'], { type: 'image/png' }), 'fashionrise-sketch.png', {
      createObjectURL: () => 'blob:fake',
      revokeObjectURL: revoke,
      schedule: (fn) => scheduled.push(fn),
    })
    expect(click).toHaveBeenCalledTimes(1)
    expect(document.querySelector('a[download]')).toBeNull()
    expect(revoke).not.toHaveBeenCalled()
    scheduled.forEach((fn) => fn())
    expect(revoke).toHaveBeenCalledWith('blob:fake')
  })

  it('revokes even when the click throws', () => {
    const revoke = vi.fn()
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(() =>
      downloadBlob(new Blob(['x']), 'a.png', {
        createObjectURL: () => 'blob:fake',
        revokeObjectURL: revoke,
        schedule: (fn) => fn(),
      }),
    ).toThrow('blocked')
    expect(revoke).toHaveBeenCalledWith('blob:fake')
  })

  it('builds safe human-readable filenames', () => {
    const now = new Date(2026, 9, 20, 9, 5)
    expect(exportFilename(null, now)).toBe('fashionrise-sketch-2026-10-20-0905.png')
    expect(exportFilename('Évening Gown / v2', now)).toBe('fashionrise-evening-gown-v2-2026-10-20-0905.png')
    expect(exportFilename('../../etc/passwd', now)).toBe('fashionrise-etc-passwd-2026-10-20-0905.png')
    expect(exportFilename('שמלה', now)).toBe('fashionrise-sketch-2026-10-20-0905.png')
  })
})
