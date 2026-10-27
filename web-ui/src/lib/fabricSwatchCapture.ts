/**
 * Capture a high-quality textile reference swatch from the actual Studio fabric
 * tile (built-in or uploaded). Used as Magic images.edit image #2.
 */
import { getCachedFabricImage, ensureFabricAssetsForFills } from '@/lib/fabricAssetCache'
import type { FillOp } from '@/lib/fills'
import {
  BUILTIN_FABRIC_TILE_PX,
  renderFabricTile,
  renderUploadedFabricTile,
} from '@/lib/paintFills'

/** Bounded swatch edge (px). Large enough to show repeat; small enough for edit payload. */
export const FABRIC_SWATCH_EDGE_PX = 512
/** Soft cap for encoded data URL length (~350KB decoded). */
export const FABRIC_SWATCH_MAX_DATA_URL_CHARS = 480_000

export type FabricSwatchCapture = {
  dataUrl: string
  /** Human-readable textile identity for garment spec / prompts. */
  label: string
  kind: 'fabric' | 'uploaded-fabric'
  fabricId?: string
  assetId?: string
  byteLength: number
}

function isPatternedFill(fill: FillOp): boolean {
  return fill.style.kind === 'fabric' || fill.style.kind === 'uploaded-fabric'
}

/** Prefer the first patterned fill on the side (dominant garment textile). */
export function dominantPatternedFill(fills: FillOp[]): FillOp | null {
  for (const f of fills) {
    if (isPatternedFill(f)) return f
  }
  return null
}

function tileOntoSwatch(tile: HTMLCanvasElement): HTMLCanvasElement {
  const edge = FABRIC_SWATCH_EDGE_PX
  const out = document.createElement('canvas')
  out.width = edge
  out.height = edge
  const ctx = out.getContext('2d')
  if (!ctx) return out
  const pattern = ctx.createPattern(tile, 'repeat')
  if (!pattern) {
    // Fallback: stretch single tile
    ctx.imageSmoothingEnabled = false
    ctx.drawImage(tile, 0, 0, edge, edge)
    return out
  }
  ctx.fillStyle = pattern
  ctx.fillRect(0, 0, edge, edge)
  return out
}

function canvasToPngDataUrl(canvas: HTMLCanvasElement): string {
  return canvas.toDataURL('image/png')
}

/**
 * Build a Magic textile reference from the same tile Studio uses when painting.
 * Returns null when there is no patterned fabric, or the uploaded asset is unavailable.
 */
export async function captureFabricSwatchForMagic(
  fills: FillOp[],
): Promise<FabricSwatchCapture | null> {
  const fill = dominantPatternedFill(fills)
  if (!fill) return null

  if (fill.style.kind === 'fabric') {
    const tile = renderFabricTile(fill.style.fabricId)
    if (!tile.width || !tile.height) return null
    // Sanity: built-in tiles must match Studio unit size.
    if (tile.width !== BUILTIN_FABRIC_TILE_PX) {
      // Still usable — proceed with whatever renderFabricTile produced.
    }
    const swatch = tileOntoSwatch(tile)
    const dataUrl = canvasToPngDataUrl(swatch)
    if (!dataUrl || dataUrl.length > FABRIC_SWATCH_MAX_DATA_URL_CHARS) return null
    const approxBytes = Math.floor((dataUrl.length * 3) / 4)
    return {
      dataUrl,
      label: `${fill.style.fabricId} repeating textile (exact Studio tile)`,
      kind: 'fabric',
      fabricId: fill.style.fabricId,
      byteLength: approxBytes,
    }
  }

  if (fill.style.kind === 'uploaded-fabric') {
    await ensureFabricAssetsForFills([fill], { required: true })
    const img = getCachedFabricImage(fill.style.assetId)
    if (!img || !img.width || !img.height) {
      throw new Error(
        'Your custom fabric could not be loaded for Magic. Re-open the design or re-upload the fabric, then try again.',
      )
    }
    const tile = renderUploadedFabricTile(img, fill.style.scale)
    const swatch = tileOntoSwatch(tile)
    const dataUrl = canvasToPngDataUrl(swatch)
    if (!dataUrl || dataUrl.length > FABRIC_SWATCH_MAX_DATA_URL_CHARS) {
      throw new Error('Fabric swatch is too large to send to Magic. Try a smaller fabric image.')
    }
    const approxBytes = Math.floor((dataUrl.length * 3) / 4)
    return {
      dataUrl,
      label: 'uploaded fabric repeating textile (exact Studio tile)',
      kind: 'uploaded-fabric',
      assetId: fill.style.assetId,
      byteLength: approxBytes,
    }
  }

  return null
}
