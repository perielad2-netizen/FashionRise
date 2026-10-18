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

/**
 * Render reference + ink into a PNG blob for future Magic/export (WEB-2).
 * Does not call any network APIs.
 */
export async function exportCompositePng(options: ExportOptions): Promise<Blob> {
  const width = options.width ?? DESIGN_WIDTH
  const height = options.height ?? DESIGN_HEIGHT
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Canvas 2D unavailable')

  ctx.fillStyle = options.background ?? '#F8F4F0'
  ctx.fillRect(0, 0, width, height)

  if (options.referenceUrl) {
    const img = await loadImage(options.referenceUrl)
    ctx.save()
    ctx.globalAlpha = options.referenceOpacity ?? 1
    const fit = fitContain(img.width, img.height, width, height)
    ctx.drawImage(img, fit.x, fit.y, fit.w, fit.h)
    ctx.restore()
  }

  for (const stroke of options.strokes) {
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

  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
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
