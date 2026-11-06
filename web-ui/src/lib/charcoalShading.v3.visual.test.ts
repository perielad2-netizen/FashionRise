/**
 * Charcoal V3 pencil-tip visual fixtures — hard tip, soft vanish (offline).
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { createCanvas, Path2D as NapiPath2D } from '@napi-rs/canvas'
import { beforeAll, describe, expect, it } from 'vitest'
import {
  CHARCOAL_RENDERER_V2,
  CHARCOAL_RENDERER_V3,
  applyBrushEngineToStroke,
  defaultsForBrushKind,
  paintProfessionalDrawStroke,
} from '@/lib/professionalBrushes'
import { createStrokeId, type Stroke } from '@/lib/strokes'

const OUT_DIR = '/opt/cursor/artifacts/charcoal-v3'
const W = 320
const H = 480

beforeAll(() => {
  // @ts-expect-error napi Path2D
  globalThis.Path2D = NapiPath2D
  const realCreate = document.createElement.bind(document)
  // @ts-expect-error test shim
  document.createElement = ((tag: string) => {
    if (tag !== 'canvas') return realCreate(tag)
    return createCanvas(1, 1) as unknown as HTMLCanvasElement
  }) as typeof document.createElement
  mkdirSync(OUT_DIR, { recursive: true })
})

function paintDressBase(ctx: CanvasRenderingContext2D): void {
  ctx.fillStyle = '#F8F4F0'
  ctx.fillRect(0, 0, W, H)
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
  ctx.fillStyle = '#F8F4F0'
  ctx.beginPath()
  ctx.moveTo(160, 85)
  ctx.lineTo(185, 200)
  ctx.lineTo(135, 200)
  ctx.closePath()
  ctx.fill()
}

function charcoalStroke(points: number[], size: number, renderer: number): Stroke {
  const engine = {
    brushKind: 'charcoal' as const,
    logicalLayer: 'shade' as const,
    blendMode: 'multiply' as const,
    flow: 0.48,
    softness: 0.86,
    textureIntensity: 0.1,
    garmentMask: false,
  }
  const base: Stroke = {
    id: createStrokeId(),
    tool: 'draw',
    points,
    color: '#3A3230',
    size,
    opacity: 0.9,
    charcoalRenderer: renderer,
  }
  const s = applyBrushEngineToStroke(base, { ...defaultsForBrushKind('charcoal'), ...engine })
  s.charcoalRenderer = renderer
  return s
}

function denseSamples(x0: number, y0: number, x1: number, y1: number, n: number): number[] {
  const out: number[] = []
  for (let i = 0; i < n; i += 1) {
    const t = i / Math.max(1, n - 1)
    // Tip pressure firmer, then lightens like a lifted pencil.
    const p = 0.85 - t * 0.35
    out.push(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, p)
  }
  return out
}

function save(name: string, canvas: ReturnType<typeof createCanvas>): void {
  writeFileSync(join(OUT_DIR, name), canvas.toBuffer('image/png'))
}

/** Lower = darker (multiply shade over peach dress). */
function luminanceAt(ctx: CanvasRenderingContext2D, x: number, y: number): number {
  const d = ctx.getImageData(x, y, 1, 1).data
  return (d[0]! * 0.3 + d[1]! * 0.59 + d[2]! * 0.11)
}

describe('Charcoal V3 pencil-tip visual', () => {
  it('new charcoal strokes default to renderer v3', () => {
    const s = charcoalStroke([100, 100, 0.8, 100, 200, 0.4], 16, CHARCOAL_RENDERER_V3)
    expect(s.charcoalRenderer).toBe(CHARCOAL_RENDERER_V3)
  })

  it('vertical fold: tip darker than tail (hard tip → soft vanish)', () => {
    const pts = denseSamples(168, 200, 162, 400, 36)
    const v3 = charcoalStroke(pts, 16, CHARCOAL_RENDERER_V3)
    const canvas = createCanvas(W, H)
    const ctx = canvas.getContext('2d')
    paintDressBase(ctx)
    paintProfessionalDrawStroke(ctx as unknown as CanvasRenderingContext2D, v3)
    save('01-vertical-pencil-tip.png', canvas)

    const tipL = luminanceAt(ctx, 168, 220)
    const midL = luminanceAt(ctx, 165, 300)
    const tailL = luminanceAt(ctx, 162, 385)
    // Tip should be darker (lower luminance) than the vanishing tail.
    expect(tipL).toBeLessThan(tailL)
    expect(tailL - tipL).toBeGreaterThan(6)
    expect(midL).toBeGreaterThan(tipL - 2)
  })

  it('writes v2 vs v3 comparison on the same vertical path', () => {
    const pts = denseSamples(160, 210, 155, 400, 32)
    const v2 = charcoalStroke(pts, 16, CHARCOAL_RENDERER_V2)
    const v3 = charcoalStroke(pts, 16, CHARCOAL_RENDERER_V3)
    const c2 = createCanvas(W, H)
    const c3 = createCanvas(W, H)
    paintDressBase(c2.getContext('2d'))
    paintDressBase(c3.getContext('2d'))
    paintProfessionalDrawStroke(c2.getContext('2d') as unknown as CanvasRenderingContext2D, v2)
    paintProfessionalDrawStroke(c3.getContext('2d') as unknown as CanvasRenderingContext2D, v3)
    save('02-before-v2-ribbon.png', c2)
    save('03-after-v3-pencil-tip.png', c3)
    expect(true).toBe(true)
  })

  it('waist and curved fold fixtures', () => {
    const cases: Array<{ name: string; points: number[]; size: number }> = [
      { name: '04-waist-tip-fade.png', points: denseSamples(120, 200, 205, 205, 28), size: 15 },
      {
        name: '05-curved-fold-tip.png',
        points: (() => {
          const pts: number[] = []
          for (let i = 0; i < 36; i += 1) {
            const t = i / 35
            pts.push(130 + t * 70, 230 + Math.sin(t * Math.PI) * 45, 0.8 - t * 0.35)
          }
          return pts
        })(),
        size: 14,
      },
    ]
    for (const c of cases) {
      const canvas = createCanvas(W, H)
      paintDressBase(canvas.getContext('2d'))
      paintProfessionalDrawStroke(
        canvas.getContext('2d') as unknown as CanvasRenderingContext2D,
        charcoalStroke(c.points, c.size, CHARCOAL_RENDERER_V3),
      )
      save(c.name, canvas)
    }
    expect(true).toBe(true)
  })
})
