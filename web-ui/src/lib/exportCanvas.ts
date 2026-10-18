import { strokeToSvgPath } from '@/lib/freehand'
import { DESIGN_HEIGHT, DESIGN_WIDTH, type Stroke } from '@/lib/strokes'

export type ExportOptions = {
  strokes: Stroke[]
  referenceUrl: string | null
  referenceOpacity?: number
  background?: string
  width?: number
  height?: number
}

export type Canvas2DLike = {
  fillStyle: string | CanvasGradient | CanvasPattern
  globalAlpha: number
  globalCompositeOperation: GlobalCompositeOperation | string
  fillRect(x: number, y: number, w: number, h: number): void
  fill(path: Path2D): void
  drawImage(
    image: CanvasImageSource,
    dx: number,
    dy: number,
    dw: number,
    dh: number,
  ): void
  save(): void
  restore(): void
}

/**
 * Paint ink strokes onto an ink-only context.
 * Eraser uses destination-out against ink pixels only — never against reference/base.
 */
export function paintInkStrokes(ctx: Canvas2DLike, strokes: Stroke[]): void {
  for (const stroke of strokes) {
    const path = strokeToSvgPath(stroke)
    if (!path) continue
    const p = new Path2D(path)
    ctx.save()
    if (stroke.tool === 'erase') {
      ctx.globalCompositeOperation = 'destination-out'
      ctx.fillStyle = 'rgba(0,0,0,1)'
    } else {
      ctx.globalCompositeOperation = 'source-over'
      ctx.globalAlpha = stroke.opacity
      ctx.fillStyle = stroke.color
    }
    ctx.fill(p)
    ctx.restore()
  }
}

/**
 * Render reference + ink into a PNG blob for future Magic/export (WEB-2).
 *
 * Architecture:
 *   BASE canvas  = background + reference
 *   INK canvas   = strokes (eraser destination-out on ink only)
 *   FINAL        = base, then ink composited on top
 *
 * Does not call any network APIs.
 */
export async function exportCompositePng(options: ExportOptions): Promise<Blob> {
  const width = options.width ?? DESIGN_WIDTH
  const height = options.height ?? DESIGN_HEIGHT

  const base = document.createElement('canvas')
  base.width = width
  base.height = height
  const baseCtx = base.getContext('2d')
  if (!baseCtx) throw new Error('Canvas 2D unavailable')

  baseCtx.fillStyle = options.background ?? '#F8F4F0'
  baseCtx.fillRect(0, 0, width, height)

  if (options.referenceUrl) {
    const img = await loadImage(options.referenceUrl)
    baseCtx.save()
    baseCtx.globalAlpha = options.referenceOpacity ?? 1
    const fit = fitContain(img.width, img.height, width, height)
    baseCtx.drawImage(img, fit.x, fit.y, fit.w, fit.h)
    baseCtx.restore()
  }

  const ink = document.createElement('canvas')
  ink.width = width
  ink.height = height
  const inkCtx = ink.getContext('2d')
  if (!inkCtx) throw new Error('Canvas 2D unavailable')

  paintInkStrokes(inkCtx, options.strokes)

  // Final composite: ink over intact base (reference never erased).
  baseCtx.drawImage(ink, 0, 0)

  return new Promise((resolve, reject) => {
    base.toBlob((blob) => {
      if (!blob) reject(new Error('PNG export failed'))
      else resolve(blob)
    }, 'image/png')
  })
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error('Failed to load reference image'))
    img.src = src
  })
}

function fitContain(
  srcW: number,
  srcH: number,
  boxW: number,
  boxH: number,
): { x: number; y: number; w: number; h: number } {
  const scale = Math.min(boxW / srcW, boxH / srcH)
  const w = srcW * scale
  const h = srcH * scale
  return { x: (boxW - w) / 2, y: (boxH - h) / 2, w, h }
}
