import { strokeToSvgPath } from '@/lib/freehand'
import type { FillOp } from '@/lib/fills'
import { ensureFabricAssetsForFills } from '@/lib/fabricAssetCache'
import { paintFillOps } from '@/lib/paintFills'
import {
  legacyExportFrame,
  paperExportFrame,
  resolveExportFrame,
  resolveSheetExportFrame,
  type ExportFrame,
} from '@/lib/paperBounds'
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
  createLinearGradient?(x0: number, y0: number, x1: number, y1: number): CanvasGradient
  createPattern?(image: CanvasImageSource, repetition: string): CanvasPattern | null
  save(): void
  restore(): void
}

type FillPaintTarget = Canvas2DLike & {
  createLinearGradient(x0: number, y0: number, x1: number, y1: number): CanvasGradient
  createPattern(image: CanvasImageSource, repetition: string): CanvasPattern | null
}

export type PaintInkOptions = {
  /**
   * When true, draw strokes use seal-tip freehand paths so fill barriers do not
   * leak at tapered joins. Erasers are unchanged. Visible Konva rendering omits
   * this flag.
   */
  sealTips?: boolean
}

/** Paint a single erase stroke with destination-out (never onto reference/base). */
export function paintEraseStroke(ctx: Canvas2DLike, stroke: Stroke): void {
  if (stroke.tool !== 'erase') return
  const path = strokeToSvgPath(stroke)
  if (!path) return
  const p = new Path2D(path)
  ctx.save()
  ctx.globalCompositeOperation = 'destination-out'
  ctx.fillStyle = 'rgba(0,0,0,1)'
  ctx.fill(p)
  ctx.restore()
}

/**
 * Paint ink strokes onto an ink-only context.
 * Eraser uses destination-out against ink pixels — never against reference/base.
 */
export function paintInkStrokes(
  ctx: Canvas2DLike,
  strokes: Stroke[],
  options?: PaintInkOptions,
): void {
  const sealTips = options?.sealTips === true
  for (const stroke of strokes) {
    const path = strokeToSvgPath(stroke, stroke.tool === 'draw' && sealTips ? { sealTips: true } : undefined)
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
 * Paint garment fills, applying eraser strokes that occurred at or after each
 * fill's `eraseAfterStrokeIndex` (missing → 0 for legacy saves). Croquis/reference
 * is never present on this context.
 */
export function paintFillsWithErasers(
  ctx: FillPaintTarget,
  fills: FillOp[],
  strokes: Stroke[],
): void {
  for (const fill of fills) {
    paintFillOps(ctx, [fill])
    const after = fill.eraseAfterStrokeIndex ?? 0
    for (let i = after; i < strokes.length; i += 1) {
      const stroke = strokes[i]!
      if (stroke.tool === 'erase') paintEraseStroke(ctx, stroke)
    }
  }
}

export type ArtworkLayerOptions = {
  fills: FillOp[]
  strokes: Stroke[]
  width: number
  height: number
  /** Design→output scale applied on each layer before paint (default 1). */
  scaleX?: number
  scaleY?: number
  /**
   * Design-space origin of the output raster (paper offset). Design (0,0) lands at
   * pixel (−originX, −originY) after scale — required for extended-paper exports.
   */
  originX?: number
  originY?: number
  /** Letterbox offset in output pixels (fit-contain padding). */
  offsetX?: number
  offsetY?: number
}

function applyDesignTransform(
  ctx: CanvasRenderingContext2D,
  options: {
    scaleX: number
    scaleY: number
    originX: number
    originY: number
    offsetX: number
    offsetY: number
  },
): void {
  const { scaleX: sx, scaleY: sy, originX: ox, originY: oy, offsetX, offsetY } = options
  if (offsetX !== 0 || offsetY !== 0) ctx.translate(offsetX, offsetY)
  if (sx !== 1 || sy !== 1) ctx.scale(sx, sy)
  if (ox !== 0 || oy !== 0) ctx.translate(-ox, -oy)
}

/**
 * Composite garment fills then ink onto `target`, matching Konva / PNG layering.
 * Fills and ink stay on separate canvases so eraser never touches the reference;
 * the same eraser strokes also punch fill pixels (per-fill chronology).
 */
export function compositeFillAndInkLayers(target: Canvas2DLike, options: ArtworkLayerOptions): void {
  const { width, height, fills, strokes } = options
  const sx = options.scaleX ?? 1
  const sy = options.scaleY ?? 1
  const ox = options.originX ?? 0
  const oy = options.originY ?? 0
  const offsetX = options.offsetX ?? 0
  const offsetY = options.offsetY ?? 0
  const needsTransform = sx !== 1 || sy !== 1 || ox !== 0 || oy !== 0 || offsetX !== 0 || offsetY !== 0

  const fillLayer = document.createElement('canvas')
  fillLayer.width = width
  fillLayer.height = height
  const fillCtx = fillLayer.getContext('2d')
  if (!fillCtx) throw new Error('Canvas 2D unavailable')
  if (needsTransform) {
    applyDesignTransform(fillCtx, { scaleX: sx, scaleY: sy, originX: ox, originY: oy, offsetX, offsetY })
  }
  paintFillsWithErasers(fillCtx, fills, strokes)
  target.drawImage(fillLayer, 0, 0, width, height)

  const inkLayer = document.createElement('canvas')
  inkLayer.width = width
  inkLayer.height = height
  const inkCtx = inkLayer.getContext('2d')
  if (!inkCtx) throw new Error('Canvas 2D unavailable')
  if (needsTransform) {
    applyDesignTransform(inkCtx, { scaleX: sx, scaleY: sy, originX: ox, originY: oy, offsetX, offsetY })
  }
  paintInkStrokes(inkCtx, strokes)
  target.drawImage(inkLayer, 0, 0, width, height)
}

/**
 * Uniform fit-contain of a design frame into an output size (letterbox / pillarbox).
 * When aspects match (legacy 768×1024 → 240×320), scale is identical to stretch and
 * offsets are zero — legacy thumbnails stay pixel-compatible.
 */
export function fitContainLayout(
  designW: number,
  designH: number,
  outW: number,
  outH: number,
): { scale: number; offsetX: number; offsetY: number; contentW: number; contentH: number } {
  const scale = Math.min(outW / Math.max(1, designW), outH / Math.max(1, designH))
  const contentW = designW * scale
  const contentH = designH * scale
  return {
    scale,
    offsetX: (outW - contentW) / 2,
    offsetY: (outH - contentH) / 2,
    contentW,
    contentH,
  }
}

export type RenderedSketch = {
  canvas: HTMLCanvasElement
  referenceIncluded: boolean
}

export type RenderOptions = ExportOptions & {
  /** 'skip' renders without the reference when it cannot be loaded; 'throw' rejects. */
  onReferenceError?: 'skip' | 'throw'
  /**
   * Uploaded-fabric policy. Export/Magic default to `throw` so incomplete artwork
   * is never silently submitted. Thumbnails may use `skip` (placeholder hatch).
   */
  onFabricError?: 'skip' | 'throw'
  loadReference?: (src: string) => Promise<CanvasImageSource & { width: number; height: number }>
  /**
   * Minimum stroke size in output pixels. Thumbnails need it because hairline brushes
   * fall below one pixel when 768×1024 is scaled down. Leave unset for exports.
   */
  minInkSize?: number
  /**
   * Design-space frame selection. Independent of `width`/`height` (output resize).
   * - `auto` (default): legacy vs paper from artwork bounds
   * - `legacy` / `paper`: force that frame (Front+Back sheet alignment)
   */
  frame?: 'auto' | 'legacy' | 'paper' | ExportFrame
}

function resolveRenderFrame(
  options: Pick<RenderOptions, 'strokes' | 'fills' | 'frame'>,
): ExportFrame {
  const fills = options.fills ?? []
  const requested = options.frame ?? 'auto'
  if (requested === 'legacy') return legacyExportFrame()
  if (requested === 'paper') return paperExportFrame()
  if (typeof requested === 'object') return requested
  return resolveExportFrame(options.strokes, fills)
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
 * Strokes stay in design space. Frame choice (`auto` / `legacy` / `paper`) is
 * independent of output `width`/`height`. When an explicit output size is set,
 * the design frame is mapped with **uniform fit-contain** (letterbox) so croquis
 * and garment proportions are preserved — critical when paper 1280×1536 is shown
 * in a 240×320 thumbnail. Legacy 768×1024 → 240×320 keeps identical scale/offsets.
 *
 * No network calls other than loading the reference image URL already shown in Studio.
 */
export async function renderSketchCanvas(options: RenderOptions): Promise<RenderedSketch> {
  const fills = options.fills ?? []
  const frame = resolveRenderFrame(options)

  const originX = frame.originX
  const originY = frame.originY
  const designW = frame.width
  const designH = frame.height
  const width = options.width ?? designW
  const height = options.height ?? designH
  const layout = fitContainLayout(designW, designH, width, height)
  const sx = layout.scale
  const sy = layout.scale
  const offsetX = layout.offsetX
  const offsetY = layout.offsetY

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
      applyDesignTransform(baseCtx, {
        scaleX: sx,
        scaleY: sy,
        originX,
        originY,
        offsetX,
        offsetY,
      })
      baseCtx.globalAlpha = options.referenceOpacity ?? 1
      baseCtx.drawImage(img, fit.x, fit.y, fit.w, fit.h)
      baseCtx.restore()
      referenceIncluded = true
    } catch (err) {
      if (options.onReferenceError !== 'skip') throw err
    }
  }

  // Prefetch private fabric assets before paint so tiling matches live Studio.
  const fabricMode = options.onFabricError ?? 'throw'
  try {
    await ensureFabricAssetsForFills(fills, { required: fabricMode === 'throw' })
  } catch (err) {
    if (fabricMode === 'throw') throw err
  }

  // Fills sit above the reference and under ink (garment colour / fabric).
  // Eraser punches fill + ink on their own layers; reference/base stays intact.
  const strokes = options.minInkSize
    ? withMinimumSize(options.strokes, options.minInkSize / Math.min(sx, sy))
    : options.strokes
  compositeFillAndInkLayers(baseCtx, {
    fills,
    strokes,
    width,
    height,
    scaleX: sx,
    scaleY: sy,
    originX,
    originY,
    offsetX,
    offsetY,
  })
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
export type FrontBackSheetOptions = {
  front: ExportOptions
  back: ExportOptions
  gapPx?: number
  labelHeightPx?: number
}

/** Side-by-side front + back sheet with simple labels (export helper). */
export async function exportFrontBackSheetPng(
  options: FrontBackSheetOptions,
): Promise<SketchPngResult> {
  const gap = options.gapPx ?? 24
  const labelH = options.labelHeightPx ?? 28
  // Shared frame so croquis alignment matches across sides; never force legacy
  // dimensions that would crop extended-margin artwork.
  const sheetFrame = resolveSheetExportFrame(
    { strokes: options.front.strokes, fills: options.front.fills },
    { strokes: options.back.strokes, fills: options.back.fills },
  )

  const [{ canvas: frontCanvas, referenceIncluded: frontRef }, { canvas: backCanvas, referenceIncluded: backRef }] =
    await Promise.all([
      renderSketchCanvas({
        ...options.front,
        // Explicit output size only when the caller asked for it; otherwise native frame.
        width: options.front.width,
        height: options.front.height,
        frame: sheetFrame,
        onReferenceError: 'skip',
      }),
      renderSketchCanvas({
        ...options.back,
        width: options.back.width,
        height: options.back.height,
        frame: sheetFrame,
        onReferenceError: 'skip',
      }),
    ])

  const frontW = frontCanvas.width
  const frontH = frontCanvas.height
  const backW = backCanvas.width
  const backH = backCanvas.height
  const panelW = Math.max(frontW, backW)
  // Preserve the historical sheet height formula (legacy layout unchanged).
  const panelH = frontH + labelH + backH + labelH
  const sheetW = panelW * 2 + gap
  const sheetH = panelH

  const sheet = document.createElement('canvas')
  sheet.width = sheetW
  sheet.height = sheetH
  const ctx = sheet.getContext('2d')
  if (!ctx) throw new Error('Canvas 2D unavailable')
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, sheetW, sheetH)

  const drawPanel = (x: number, label: string, canvas: HTMLCanvasElement) => {
    ctx.fillStyle = '#3a3a3c'
    ctx.font = '600 14px system-ui, sans-serif'
    ctx.fillText(label, x + 8, 20)
    const y = labelH
    ctx.drawImage(canvas, x + (panelW - canvas.width) / 2, y)
  }
  drawPanel(0, 'Front', frontCanvas)
  drawPanel(panelW + gap, 'Back', backCanvas)
  const blob = await canvasToPngBlob(sheet)
  return { blob, referenceIncluded: frontRef || backRef }
}

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
