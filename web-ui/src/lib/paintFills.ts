import { getCachedFabricImage, registerFabricCacheClearHook } from '@/lib/fabricAssetCache'
import {
  contourToSvgPath,
  type FabricFillStyle,
  type FillOp,
  type FillStyle,
  type GradientFillStyle,
  type UploadedFabricFillStyle,
} from '@/lib/fills'

export type FillPaintContext = {
  fillStyle: string | CanvasGradient | CanvasPattern
  globalAlpha: number
  fill(path: Path2D): void
  createLinearGradient(x0: number, y0: number, x1: number, y1: number): CanvasGradient
  createPattern(image: CanvasImageSource, repetition: string): CanvasPattern | null
  save(): void
  restore(): void
}

/**
 * Paint fill regions under ink. Shared by live preview canvases and PNG/Magic export.
 */
export function paintFillOps(ctx: FillPaintContext, fills: FillOp[]): void {
  for (const fill of fills) {
    const d = contourToSvgPath(fill.contour)
    if (!d) continue
    const path = new Path2D(d)
    ctx.save()
    ctx.globalAlpha = 1
    ctx.fillStyle = resolveFillStyle(ctx, fill)
    ctx.fill(path)
    ctx.restore()
  }
}

function resolveFillStyle(ctx: FillPaintContext, fill: FillOp): string | CanvasGradient | CanvasPattern {
  const style = fill.style
  if (style.kind === 'solid') return style.color
  if (style.kind === 'gradient') return makeGradient(ctx, fill.contour, style)
  if (style.kind === 'uploaded-fabric') {
    return makeUploadedFabricPattern(ctx, style) ?? missingFabricPlaceholder(ctx)
  }
  return makeFabricPattern(ctx, style) ?? '#CCCCCC'
}

function missingFabricPlaceholder(ctx: FillPaintContext): CanvasPattern | string {
  const tile = document.createElement('canvas')
  tile.width = 16
  tile.height = 16
  const t = tile.getContext('2d')
  if (!t) return '#C4B5C8'
  t.fillStyle = '#E7E0E8'
  t.fillRect(0, 0, 16, 16)
  t.strokeStyle = '#BE185D'
  t.lineWidth = 2
  t.beginPath()
  t.moveTo(0, 16)
  t.lineTo(16, 0)
  t.stroke()
  return ctx.createPattern(tile, 'repeat') ?? '#C4B5C8'
}

function contourBounds(contour: number[]): { minX: number; minY: number; maxX: number; maxY: number } {
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (let i = 0; i < contour.length; i += 2) {
    const x = contour[i]!
    const y = contour[i + 1]!
    if (x < minX) minX = x
    if (y < minY) minY = y
    if (x > maxX) maxX = x
    if (y > maxY) maxY = y
  }
  return { minX, minY, maxX, maxY }
}

function makeGradient(
  ctx: FillPaintContext,
  contour: number[],
  style: GradientFillStyle,
): CanvasGradient {
  const b = contourBounds(contour)
  const cx = (b.minX + b.maxX) / 2
  const cy = (b.minY + b.maxY) / 2
  const len = Math.hypot(b.maxX - b.minX, b.maxY - b.minY) / 2 || 1
  const rad = (style.angle * Math.PI) / 180
  const dx = Math.cos(rad) * len
  const dy = Math.sin(rad) * len
  const g = ctx.createLinearGradient(cx - dx, cy - dy, cx + dx, cy + dy)
  g.addColorStop(0, style.colors[0])
  g.addColorStop(1, style.colors[1])
  return g
}

const fabricTileCache = new Map<string, HTMLCanvasElement>()

function makeFabricPattern(ctx: FillPaintContext, style: FabricFillStyle): CanvasPattern | null {
  let tile = fabricTileCache.get(style.fabricId)
  if (!tile) {
    tile = renderFabricTile(style.fabricId)
    fabricTileCache.set(style.fabricId, tile)
  }
  return ctx.createPattern(tile, 'repeat')
}

const uploadedTileCache = new Map<string, HTMLCanvasElement>()

/** Fashion-sized base repeat unit (design px). Scale multiplies this — not raw image size —
 * so 0.25× / 1× / 4× stay distinct even for 2048×2048 uploads (avoids 512px saturation). */
export const UPLOADED_FABRIC_BASE_TILE_PX = 128
export const UPLOADED_FABRIC_TILE_MIN_PX = 24
export const UPLOADED_FABRIC_TILE_MAX_PX = 512

/** Drop derived pattern tiles (call when the signed-in account changes). */
export function clearUploadedFabricTileCache(): void {
  uploadedTileCache.clear()
}

registerFabricCacheClearHook(clearUploadedFabricTileCache)

function makeUploadedFabricPattern(
  ctx: FillPaintContext,
  style: UploadedFabricFillStyle,
): CanvasPattern | null {
  const img = getCachedFabricImage(style.assetId)
  if (!img) return null
  const key = `${style.assetId.toLowerCase()}:${style.scale.toFixed(3)}`
  let tile = uploadedTileCache.get(key)
  if (!tile) {
    tile = renderUploadedFabricTile(img, style.scale)
    uploadedTileCache.set(key, tile)
  }
  return ctx.createPattern(tile, 'repeat')
}

/**
 * Deterministic, memory-bounded tile for uploaded fabrics.
 * target = clamp(round(BASE_TILE × scale), MIN, MAX) — independent of source resolution.
 */
export function renderUploadedFabricTile(img: HTMLImageElement, scale: number): HTMLCanvasElement {
  const safeScale = Number.isFinite(scale) ? scale : 1
  const target = Math.round(
    Math.min(
      UPLOADED_FABRIC_TILE_MAX_PX,
      Math.max(UPLOADED_FABRIC_TILE_MIN_PX, UPLOADED_FABRIC_BASE_TILE_PX * safeScale),
    ),
  )
  const aspect = img.width / Math.max(1, img.height)
  const w = aspect >= 1 ? target : Math.max(UPLOADED_FABRIC_TILE_MIN_PX, Math.round(target * aspect))
  const h = aspect >= 1 ? Math.max(UPLOADED_FABRIC_TILE_MIN_PX, Math.round(target / aspect)) : target
  const c = document.createElement('canvas')
  c.width = w
  c.height = h
  const tileCtx = c.getContext('2d')
  if (!tileCtx) return c
  tileCtx.imageSmoothingEnabled = true
  tileCtx.drawImage(img, 0, 0, w, h)
  return c
}

/** Built-in fabric tile size used by Studio fill patterns (exact Magic swatch source). */
export const BUILTIN_FABRIC_TILE_PX = 64

/** Render the exact built-in fabric tile shown on the Studio canvas (source of truth). */
export function renderFabricTile(fabricId: string): HTMLCanvasElement {
  const size = BUILTIN_FABRIC_TILE_PX
  const c = document.createElement('canvas')
  c.width = size
  c.height = size
  const ctx = c.getContext('2d')
  if (!ctx) return c

  switch (fabricId) {
    case 'satin': {
      const g = ctx.createLinearGradient(0, 0, size, size)
      g.addColorStop(0, '#FFF7FB')
      g.addColorStop(0.35, '#F9A8D4')
      g.addColorStop(0.55, '#BE185D')
      g.addColorStop(0.75, '#FBCFE8')
      g.addColorStop(1, '#FFF1F8')
      ctx.fillStyle = g
      ctx.fillRect(0, 0, size, size)
      ctx.globalAlpha = 0.18
      for (let i = -size; i < size * 2; i += 6) {
        ctx.strokeStyle = '#FFFFFF'
        ctx.beginPath()
        ctx.moveTo(i, 0)
        ctx.lineTo(i + size, size)
        ctx.stroke()
      }
      break
    }
    case 'denim': {
      ctx.fillStyle = '#1E3A8A'
      ctx.fillRect(0, 0, size, size)
      ctx.strokeStyle = 'rgba(147,197,253,0.35)'
      ctx.lineWidth = 1
      for (let i = -size; i < size * 2; i += 4) {
        ctx.beginPath()
        ctx.moveTo(i, 0)
        ctx.lineTo(i + size, size)
        ctx.stroke()
      }
      ctx.fillStyle = 'rgba(15,23,42,0.25)'
      for (let y = 0; y < size; y += 3) {
        for (let x = (y % 6 === 0 ? 0 : 2); x < size; x += 4) {
          ctx.fillRect(x, y, 1, 1)
        }
      }
      break
    }
    case 'cotton': {
      ctx.fillStyle = '#E7D3B8'
      ctx.fillRect(0, 0, size, size)
      for (let i = 0; i < 180; i += 1) {
        const x = (i * 17) % size
        const y = (i * 29) % size
        ctx.fillStyle = i % 2 === 0 ? 'rgba(196,164,132,0.45)' : 'rgba(255,255,255,0.35)'
        ctx.fillRect(x, y, 1, 1)
      }
      break
    }
    case 'lace': {
      ctx.fillStyle = '#FDF2F8'
      ctx.fillRect(0, 0, size, size)
      ctx.fillStyle = '#FCE7F3'
      for (let y = 4; y < size; y += 10) {
        for (let x = 4; x < size; x += 10) {
          ctx.beginPath()
          ctx.arc(x, y, 2.2, 0, Math.PI * 2)
          ctx.fill()
          ctx.globalCompositeOperation = 'destination-out'
          ctx.beginPath()
          ctx.arc(x, y, 1.1, 0, Math.PI * 2)
          ctx.fill()
          ctx.globalCompositeOperation = 'source-over'
        }
      }
      ctx.strokeStyle = 'rgba(244,114,182,0.45)'
      ctx.strokeRect(1, 1, size - 2, size - 2)
      break
    }
    case 'floral': {
      ctx.fillStyle = '#FEF3C7'
      ctx.fillRect(0, 0, size, size)
      const flowers: [number, number, string][] = [
        [16, 18, '#FB7185'],
        [44, 22, '#F472B6'],
        [28, 44, '#F43F5E'],
        [50, 48, '#FB7185'],
      ]
      for (const [fx, fy, color] of flowers) {
        ctx.fillStyle = color
        for (let a = 0; a < 5; a += 1) {
          const ang = (a / 5) * Math.PI * 2
          ctx.beginPath()
          ctx.arc(fx + Math.cos(ang) * 5, fy + Math.sin(ang) * 5, 3.2, 0, Math.PI * 2)
          ctx.fill()
        }
        ctx.fillStyle = '#FDE68A'
        ctx.beginPath()
        ctx.arc(fx, fy, 2.2, 0, Math.PI * 2)
        ctx.fill()
      }
      break
    }
    case 'sequins': {
      ctx.fillStyle = '#7C2D12'
      ctx.fillRect(0, 0, size, size)
      for (let y = 6; y < size; y += 12) {
        for (let x = 6 + ((y / 12) % 2) * 6; x < size; x += 12) {
          const g = ctx.createRadialGradient(x - 1, y - 1, 0.5, x, y, 5)
          g.addColorStop(0, '#FEF3C7')
          g.addColorStop(0.45, '#FBBF24')
          g.addColorStop(1, '#B45309')
          ctx.fillStyle = g
          ctx.beginPath()
          ctx.arc(x, y, 4.2, 0, Math.PI * 2)
          ctx.fill()
        }
      }
      break
    }
    default: {
      ctx.fillStyle = '#CCCCCC'
      ctx.fillRect(0, 0, size, size)
    }
  }
  return c
}

/** Sample a CSS color string from a fill style (eyedropper approximation). */
export function sampleColorFromStyle(style: FillStyle): string {
  if (style.kind === 'solid') return style.color
  if (style.kind === 'gradient') return style.colors[0]
  if (style.kind === 'uploaded-fabric') return '#BE185D'
  switch (style.fabricId) {
    case 'satin':
      return '#BE185D'
    case 'denim':
      return '#1E3A8A'
    case 'cotton':
      return '#C4A484'
    case 'lace':
      return '#F9A8D4'
    case 'floral':
      return '#FB7185'
    case 'sequins':
      return '#B45309'
    default:
      return '#888888'
  }
}
