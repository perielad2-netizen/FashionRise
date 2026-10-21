import { strokeToSvgPath } from '@/lib/freehand'
import type { FillOp } from '@/lib/fills'
import { paintFillOps } from '@/lib/paintFills'
import { DESIGN_HEIGHT, DESIGN_WIDTH, type Stroke } from '@/lib/strokes'

export const PAPER_BACKGROUND = '#F8F4F0'
const REFERENCE_TIMEOUT_MS = 10_000

export type ExportOptions = {
  strokes: Stroke[]
  fills?: FillOp[]
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

export type RenderedSketch = {
  canvas: HTMLCanvasElement
  referenceIncluded: boolean
}

export type RenderOptions = ExportOptions & {
  /** 'skip' renders without the reference when it cannot be loaded; 'throw' rejects. */
  onReferenceError?: 'skip' | 'throw'
  loadReference?: (src: string) => Promise<CanvasImageSource & { width: number; height: number }>
  /**
   * Minimum stroke size in output pixels. Thumbnails need it because hairline brushes
   * fall below one pixel when 768×1024 is scaled down. Leave unset for exports.
   */
  minInkSize?: number
}

export function withMinimumSize(strokes: Stroke[], minDesignSize: number): Stroke[] {
  return strokes.map((stroke) =>
    stroke.size >= minDesignSize ? stroke : { ...stroke, size: minDesignSize },
  )
}

/**
 * Render reference + ink onto a canvas, matching the on-screen Konva composition.
 *
 *   BASE canvas  = background + reference (fit-contain in 768×1024 design space)
 *   INK canvas   = strokes (eraser destination-out on ink only)
 *   FINAL        = base, then ink composited on top
 *
 * Strokes stay in design space and are scaled to the output size. No network calls
 * other than loading the reference image URL that is already shown in Studio.
 */
export async function renderSketchCanvas(options: RenderOptions): Promise<RenderedSketch> {
  const width = options.width ?? DESIGN_WIDTH
  const height = options.height ?? DESIGN_HEIGHT
  const sx = width / DESIGN_WIDTH
  const sy = height / DESIGN_HEIGHT

  const base = document.createElement('canvas')
  base.width = width
  base.height = height
  const baseCtx = base.getContext('2d')
  if (!baseCtx) throw new Error('Canvas 2D unavailable')

  baseCtx.fillStyle = options.background ?? PAPER_BACKGROUND
  baseCtx.fillRect(0, 0, width, height)

  let referenceIncluded = false
  if (options.referenceUrl) {
    try {
      const img = await (options.loadReference ?? loadImage)(options.referenceUrl)
      const fit = fitContain(img.width, img.height, DESIGN_WIDTH, DESIGN_HEIGHT)
      baseCtx.save()
      baseCtx.globalAlpha = options.referenceOpacity ?? 1
      baseCtx.drawImage(img, fit.x * sx, fit.y * sy, fit.w * sx, fit.h * sy)
      baseCtx.restore()
      referenceIncluded = true
    } catch (err) {
      if (options.onReferenceError !== 'skip') throw err
    }
  }

  // Fills sit above the reference and under ink (garment colour / fabric).
  const fillLayer = document.createElement('canvas')
  fillLayer.width = width
  fillLayer.height = height
  const fillCtx = fillLayer.getContext('2d')
  if (!fillCtx) throw new Error('Canvas 2D unavailable')
  if (sx !== 1 || sy !== 1) fillCtx.scale(sx, sy)
  paintFillOps(fillCtx, options.fills ?? [])
  baseCtx.drawImage(fillLayer, 0, 0, width, height)

  const ink = document.createElement('canvas')
  ink.width = width
  ink.height = height
  const inkCtx = ink.getContext('2d')
  if (!inkCtx) throw new Error('Canvas 2D unavailable')
  if (sx !== 1 || sy !== 1) inkCtx.scale(sx, sy)

  const strokes = options.minInkSize
    ? withMinimumSize(options.strokes, options.minInkSize / Math.min(sx, sy))
    : options.strokes
  paintInkStrokes(inkCtx, strokes)

  baseCtx.drawImage(ink, 0, 0, width, height)
  return { canvas: base, referenceIncluded }
}

export function canvasToPngBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob || blob.size === 0) reject(new Error('PNG export failed'))
      else if (blob.type && blob.type !== 'image/png') reject(new Error('PNG export failed'))
      else resolve(blob)
    }, 'image/png')
  })
}

/** Reference failures reject; used where a partial image is not acceptable. */
export async function exportCompositePng(options: ExportOptions): Promise<Blob> {
  const { canvas } = await renderSketchCanvas({ ...options, onReferenceError: 'throw' })
  return canvasToPngBlob(canvas)
}

export type SketchPngResult = { blob: Blob; referenceIncluded: boolean }

/** Customer-facing export: a reference that fails to load is omitted, never fatal. */
export async function exportSketchPng(options: RenderOptions): Promise<SketchPngResult> {
  const { canvas, referenceIncluded } = await renderSketchCanvas({
    ...options,
    onReferenceError: options.onReferenceError ?? 'skip',
  })
  const blob = await canvasToPngBlob(canvas)
  return { blob, referenceIncluded }
}

/** `fashionrise-<title>-YYYY-MM-DD-HHMM.png`, ASCII-only and filesystem-safe. */
export function exportFilename(title: string | null, now = new Date()): string {
  const slug = (title ?? '')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48)
    .replace(/-+$/g, '')
  const pad = (n: number) => String(n).padStart(2, '0')
  const stamp = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}-${pad(
    now.getHours(),
  )}${pad(now.getMinutes())}`
  return `fashionrise-${slug || 'sketch'}-${stamp}.png`
}

export type DownloadDeps = {
  createObjectURL?: (blob: Blob) => string
  revokeObjectURL?: (url: string) => void
  schedule?: (fn: () => void, ms: number) => unknown
}

/** Trigger a browser download and always release the object URL afterwards. */
export function downloadBlob(blob: Blob, filename: string, deps: DownloadDeps = {}): void {
  const create = deps.createObjectURL ?? ((b: Blob) => URL.createObjectURL(b))
  const revoke = deps.revokeObjectURL ?? ((u: string) => URL.revokeObjectURL(u))
  const schedule = deps.schedule ?? ((fn: () => void, ms: number) => window.setTimeout(fn, ms))
  const url = create(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.rel = 'noopener'
  anchor.style.display = 'none'
  try {
    document.body.appendChild(anchor)
    anchor.click()
  } finally {
    anchor.remove()
    // iOS Safari reads the blob asynchronously after click(); revoke on the next turn.
    schedule(() => revoke(url), 1000)
  }
}

export function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    const timer = window.setTimeout(() => {
      img.src = ''
      reject(new Error('Reference image timed out'))
    }, REFERENCE_TIMEOUT_MS)
    img.onload = () => {
      window.clearTimeout(timer)
      if (!img.width || !img.height) reject(new Error('Failed to load reference image'))
      else resolve(img)
    }
    img.onerror = () => {
      window.clearTimeout(timer)
      reject(new Error('Failed to load reference image'))
    }
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
