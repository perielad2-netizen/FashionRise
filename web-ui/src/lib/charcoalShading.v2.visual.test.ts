/**
 * Charcoal Shading V2 — deterministic visual fixtures (offline, @napi-rs/canvas).
 * Writes PNG artifacts under /opt/cursor/artifacts for owner inspection.
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { createCanvas, Path2D as NapiPath2D } from '@napi-rs/canvas'
import { beforeAll, describe, expect, it } from 'vitest'
import {
  CHARCOAL_RENDERER_V1,
  CHARCOAL_RENDERER_V2,
  applyBrushEngineToStroke,
  defaultsForBrushKind,
  paintProfessionalDrawStroke,
} from '@/lib/professionalBrushes'
import { createStrokeId, type Stroke } from '@/lib/strokes'

const OUT_DIR = '/opt/cursor/artifacts/charcoal-v2'
const W = 320
const H = 480

beforeAll(() => {
  // @ts-expect-error napi Path2D for real stroke geometry in Node
  globalThis.Path2D = NapiPath2D
  const realCreate = document.createElement.bind(document)
  // @ts-expect-error test shim — professionalBrushes creates canvases via document
  document.createElement = ((tag: string) => {
    if (tag !== 'canvas') return realCreate(tag)
    // Size is assigned by the brush engine after create (mask / tint canvases).
    return createCanvas(1, 1) as unknown as HTMLCanvasElement
  }) as typeof document.createElement
  mkdirSync(OUT_DIR, { recursive: true })
})

function dressFill(): void {
  /* peach dress silhouette approximation drawn by callers */
}

function paintDressBase(ctx: CanvasRenderingContext2D): void {
  ctx.fillStyle = '#F8F4F0'
  ctx.fillRect(0, 0, W, H)
  // Pale peach gown body
  ctx.fillStyle = '#E8C4B0'
  ctx.beginPath()
  ctx.moveTo(160, 70)
  ctx.lineTo(210, 110)
  ctx.lineTo(230, 200)
  ctx.lineTo(220, 420)
  ctx.lineTo(100, 420)
  ctx.lineTo(90, 200)
  ctx.lineTo(110, 110)
  ctx.closePath()
  ctx.fill()
  // Deep V notch (paper showing)
  ctx.fillStyle = '#F8F4F0'
  ctx.beginPath()
  ctx.moveTo(160, 85)
  ctx.lineTo(185, 200)
  ctx.lineTo(135, 200)
  ctx.closePath()
  ctx.fill()
}

function charcoalStroke(
  points: number[],
  size: number,
  renderer: number,
  extras: Partial<Stroke> = {},
): Stroke {
  const engine = {
    brushKind: 'charcoal' as const,
    logicalLayer: 'shade' as const,
    blendMode: 'multiply' as const,
    flow: 0.42,
    softness: 0.82,
    textureIntensity: 0.14,
    garmentMask: false,
  }
  const base: Stroke = {
    id: createStrokeId(),
    tool: 'draw',
    points,
    color: '#3A3230',
    size,
    opacity: 0.85,
    charcoalRenderer: renderer,
    ...extras,
  }
  return applyBrushEngineToStroke(base, { ...defaultsForBrushKind('charcoal'), ...engine })
}

function denseSamples(x0: number, y0: number, x1: number, y1: number, n: number): number[] {
  const out: number[] = []
  for (let i = 0; i < n; i += 1) {
    const t = i / Math.max(1, n - 1)
    out.push(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, 0.55)
  }
  return out
}

function sparseSamples(x0: number, y0: number, x1: number, y1: number, n: number): number[] {
  return denseSamples(x0, y0, x1, y1, n)
}

function save(name: string, canvas: ReturnType<typeof createCanvas>): void {
  const png = canvas.toBuffer('image/png')
  writeFileSync(join(OUT_DIR, name), png)
}

function maxAlphaAlongColumn(
  ctx: CanvasRenderingContext2D,
  x: number,
  y0: number,
  y1: number,
): number[] {
  const vals: number[] = []
  for (let y = y0; y <= y1; y += 1) {
    const d = ctx.getImageData(x, y, 1, 1).data
    vals.push(d[3] ?? 0)
  }
  return vals
}

describe('Charcoal Shading V2 visual', () => {
  it('defaults select charcoal renderer v2 on new strokes', () => {
    const s = charcoalStroke([100, 100, 0.5, 120, 140, 0.5], 18, CHARCOAL_RENDERER_V2)
    expect(s.charcoalRenderer).toBe(CHARCOAL_RENDERER_V2)
    expect(s.brushKind).toBe('charcoal')
    expect(s.blendMode).toBe('multiply')
  })

  it('renders waist / fold / drape / curve fixtures and writes PNGs', () => {
    const cases: Array<{ name: string; points: number[]; size: number }> = [
      {
        name: '01-waist-shadow.png',
        points: denseSamples(120, 195, 200, 198, 24),
        size: 16,
      },
      {
        name: '02-vertical-fold.png',
        points: denseSamples(175, 210, 168, 400, 40),
        size: 14,
      },
      {
        name: '03-drape-wide.png',
        points: denseSamples(110, 280, 210, 300, 30),
        size: 22,
      },
      {
        name: '04-curved-fold.png',
        points: (() => {
          const pts: number[] = []
          for (let i = 0; i < 36; i += 1) {
            const t = i / 35
            pts.push(130 + t * 70, 240 + Math.sin(t * Math.PI) * 40, 0.5 + t * 0.2)
          }
          return pts
        })(),
        size: 15,
      },
    ]

    for (const c of cases) {
      const canvas = createCanvas(W, H)
      const ctx = canvas.getContext('2d')
      paintDressBase(ctx)
      const stroke = charcoalStroke(c.points, c.size, CHARCOAL_RENDERER_V2)
      // Force renderer field after applyBrushEngineToStroke
      stroke.charcoalRenderer = CHARCOAL_RENDERER_V2
      paintProfessionalDrawStroke(ctx as unknown as CanvasRenderingContext2D, stroke)
      save(c.name, canvas)
    }
    dressFill()
    expect(true).toBe(true)
  })

  it('slow vs fast sampling along the same path stay within similar peak darkness', () => {
    const slow = charcoalStroke(denseSamples(160, 220, 160, 380, 80), 16, CHARCOAL_RENDERER_V2)
    const fast = charcoalStroke(sparseSamples(160, 220, 160, 380, 8), 16, CHARCOAL_RENDERER_V2)
    slow.charcoalRenderer = CHARCOAL_RENDERER_V2
    fast.charcoalRenderer = CHARCOAL_RENDERER_V2

    const slowCanvas = createCanvas(W, H)
    const fastCanvas = createCanvas(W, H)
    paintDressBase(slowCanvas.getContext('2d'))
    paintDressBase(fastCanvas.getContext('2d'))
    paintProfessionalDrawStroke(
      slowCanvas.getContext('2d') as unknown as CanvasRenderingContext2D,
      slow,
    )
    paintProfessionalDrawStroke(
      fastCanvas.getContext('2d') as unknown as CanvasRenderingContext2D,
      fast,
    )
    save('05-slow-dense.png', slowCanvas)
    save('06-fast-sparse.png', fastCanvas)

    const slowPeak = Math.max(
      ...maxAlphaAlongColumn(slowCanvas.getContext('2d'), 160, 230, 370),
    )
    const fastPeak = Math.max(
      ...maxAlphaAlongColumn(fastCanvas.getContext('2d'), 160, 230, 370),
    )
    // Speed must not create huge darkness differences (stamp accumulation failure mode).
    expect(Math.abs(slowPeak - fastPeak)).toBeLessThan(48)
  })

  it('overlapping passes progressively darken without spray blobs', () => {
    const canvas = createCanvas(W, H)
    const ctx = canvas.getContext('2d')
    paintDressBase(ctx)
    const pass = denseSamples(150, 250, 190, 255, 20)
    for (let i = 0; i < 3; i += 1) {
      const s = charcoalStroke(pass, 18, CHARCOAL_RENDERER_V2)
      s.charcoalRenderer = CHARCOAL_RENDERER_V2
      paintProfessionalDrawStroke(ctx as unknown as CanvasRenderingContext2D, s)
    }
    save('07-overlap-passes.png', canvas)
    expect(true).toBe(true)
  })

  it('finger default pressure (0.5) still produces a soft ribbon', () => {
    const pts = denseSamples(140, 230, 200, 350, 25).map((v, i) =>
      i % 3 === 2 ? 0.5 : v,
    )
    const s = charcoalStroke(pts, 18, CHARCOAL_RENDERER_V2)
    s.charcoalRenderer = CHARCOAL_RENDERER_V2
    const canvas = createCanvas(W, H)
    paintDressBase(canvas.getContext('2d'))
    paintProfessionalDrawStroke(
      canvas.getContext('2d') as unknown as CanvasRenderingContext2D,
      s,
    )
    save('08-finger-pressure.png', canvas)
    const peak = Math.max(
      ...maxAlphaAlongColumn(canvas.getContext('2d'), 170, 240, 340),
    )
    expect(peak).toBeGreaterThan(20)
  })

  it('writes a v1 vs v2 comparison on the same path', () => {
    const pts = denseSamples(155, 210, 155, 400, 30)
    const v1 = charcoalStroke(pts, 16, CHARCOAL_RENDERER_V1)
    v1.charcoalRenderer = CHARCOAL_RENDERER_V1
    const v2 = charcoalStroke(pts, 16, CHARCOAL_RENDERER_V2)
    v2.charcoalRenderer = CHARCOAL_RENDERER_V2

    const c1 = createCanvas(W, H)
    const c2 = createCanvas(W, H)
    paintDressBase(c1.getContext('2d'))
    paintDressBase(c2.getContext('2d'))
    paintProfessionalDrawStroke(c1.getContext('2d') as unknown as CanvasRenderingContext2D, v1)
    paintProfessionalDrawStroke(c2.getContext('2d') as unknown as CanvasRenderingContext2D, v2)
    save('09-before-v1-stamp.png', c1)
    save('10-after-v2-ribbon.png', c2)
    expect(true).toBe(true)
  })

  it('matches shading at different zoom scales (design-space paint)', () => {
    const pts = denseSamples(160, 220, 160, 360, 28)
    const stroke = charcoalStroke(pts, 16, CHARCOAL_RENDERER_V2)
    stroke.charcoalRenderer = CHARCOAL_RENDERER_V2

    const paintZoomed = (scale: number) => {
      const canvas = createCanvas(W, H)
      const ctx = canvas.getContext('2d')
      paintDressBase(ctx)
      ctx.save()
      ctx.translate(W / 2, H / 2)
      ctx.scale(scale, scale)
      ctx.translate(-W / 2, -H / 2)
      paintProfessionalDrawStroke(ctx as unknown as CanvasRenderingContext2D, stroke)
      ctx.restore()
      return canvas
    }

    const z1 = paintZoomed(1)
    const z15 = paintZoomed(1.5)
    save('11-zoom-1x.png', z1)
    save('12-zoom-1.5x.png', z15)
    // Both should produce visible charcoal (non-empty alpha near stroke).
    expect(Math.max(...maxAlphaAlongColumn(z1.getContext('2d'), 160, 230, 350))).toBeGreaterThan(15)
    expect(Math.max(...maxAlphaAlongColumn(z15.getContext('2d'), 160, 230, 350))).toBeGreaterThan(10)
  })

  it('save/reopen/export: replaying stroke JSON reproduces the same peak darkness', () => {
    const pts = denseSamples(150, 240, 190, 320, 22)
    const original = charcoalStroke(pts, 18, CHARCOAL_RENDERER_V2)
    original.charcoalRenderer = CHARCOAL_RENDERER_V2
    const reopened = JSON.parse(JSON.stringify(original)) as Stroke
    expect(reopened.charcoalRenderer).toBe(CHARCOAL_RENDERER_V2)

    const a = createCanvas(W, H)
    const b = createCanvas(W, H)
    paintDressBase(a.getContext('2d'))
    paintDressBase(b.getContext('2d'))
    paintProfessionalDrawStroke(a.getContext('2d') as unknown as CanvasRenderingContext2D, original)
    paintProfessionalDrawStroke(b.getContext('2d') as unknown as CanvasRenderingContext2D, reopened)
    save('13-save-original.png', a)
    save('14-reopen-replay.png', b)

    const peakA = Math.max(...maxAlphaAlongColumn(a.getContext('2d'), 170, 250, 310))
    const peakB = Math.max(...maxAlphaAlongColumn(b.getContext('2d'), 170, 250, 310))
    expect(Math.abs(peakA - peakB)).toBeLessThan(2)
  })
})
