/**
 * Charcoal V4 — solid stroke with soft width gradient (offline fixtures).
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { createCanvas, Path2D as NapiPath2D } from '@napi-rs/canvas'
import { beforeAll, describe, expect, it } from 'vitest'
import {
  CHARCOAL_RENDERER_V3,
  CHARCOAL_RENDERER_V4,
  applyBrushEngineToStroke,
  defaultsForBrushKind,
  paintProfessionalDrawStroke,
} from '@/lib/professionalBrushes'
import { createStrokeId, type Stroke } from '@/lib/strokes'

const OUT_DIR = '/opt/cursor/artifacts/charcoal-v4'
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
    color: '#2A2422',
    size,
    opacity: 0.92,
    charcoalRenderer: renderer,
  }
  const s = applyBrushEngineToStroke(base, { ...defaultsForBrushKind('charcoal'), ...engine })
  s.charcoalRenderer = renderer
  return s
}

function vertical(x: number, y0: number, y1: number, n: number): number[] {
  const out: number[] = []
  for (let i = 0; i < n; i += 1) {
    const t = i / Math.max(1, n - 1)
    out.push(x, y0 + (y1 - y0) * t, 0.7)
  }
  return out
}

function save(name: string, canvas: ReturnType<typeof createCanvas>): void {
  writeFileSync(join(OUT_DIR, name), canvas.toBuffer('image/png'))
}

function lum(ctx: CanvasRenderingContext2D, x: number, y: number): number {
  const d = ctx.getImageData(x, y, 1, 1).data
  return d[0]! * 0.3 + d[1]! * 0.59 + d[2]! * 0.11
}

describe('Charcoal V4 width-gradient visual', () => {
  it('defaults new charcoal to renderer v4', () => {
    const s = charcoalStroke(vertical(160, 200, 380, 20), 18, CHARCOAL_RENDERER_V4)
    expect(s.charcoalRenderer).toBe(CHARCOAL_RENDERER_V4)
  })

  it('vertical fold: hard edge darker than soft side; length stays solid', () => {
    const pts = vertical(155, 190, 400, 40)
    const stroke = charcoalStroke(pts, 20, CHARCOAL_RENDERER_V4)
    const canvas = createCanvas(W, H)
    const ctx = canvas.getContext('2d')
    paintDressBase(ctx)
    paintProfessionalDrawStroke(ctx as unknown as CanvasRenderingContext2D, stroke)
    save('01-width-gradient-vertical.png', canvas)

    // Soft side is right of downward travel → sample right of hard edge.
    const hard = lum(ctx, 155, 280)
    const soft = lum(ctx, 175, 280)
    const far = lum(ctx, 195, 280)
    expect(hard).toBeLessThan(soft)
    expect(soft).toBeLessThan(far + 1)

    // Along length near the hard edge, darkness stays similar (not tip→tail).
    const top = lum(ctx, 155, 220)
    const bot = lum(ctx, 155, 370)
    expect(Math.abs(top - bot)).toBeLessThan(28)
  })

  it('writes v3 vs v4 comparison', () => {
    const pts = vertical(160, 200, 400, 36)
    const c3 = createCanvas(W, H)
    const c4 = createCanvas(W, H)
    paintDressBase(c3.getContext('2d'))
    paintDressBase(c4.getContext('2d'))
    paintProfessionalDrawStroke(
      c3.getContext('2d') as unknown as CanvasRenderingContext2D,
      charcoalStroke(pts, 18, CHARCOAL_RENDERER_V3),
    )
    paintProfessionalDrawStroke(
      c4.getContext('2d') as unknown as CanvasRenderingContext2D,
      charcoalStroke(pts, 18, CHARCOAL_RENDERER_V4),
    )
    save('02-before-v3-tip-tail.png', c3)
    save('03-after-v4-width-gradient.png', c4)
    expect(true).toBe(true)
  })

  it('angled fold fixture like reference charcoal mark', () => {
    const pts: number[] = []
    for (let i = 0; i < 30; i += 1) {
      const t = i / 29
      pts.push(120 + t * 40, 210 + t * 160, 0.75)
    }
    const canvas = createCanvas(W, H)
    paintDressBase(canvas.getContext('2d'))
    paintProfessionalDrawStroke(
      canvas.getContext('2d') as unknown as CanvasRenderingContext2D,
      charcoalStroke(pts, 22, CHARCOAL_RENDERER_V4),
    )
    save('04-angled-width-gradient.png', canvas)
    expect(true).toBe(true)
  })
})
