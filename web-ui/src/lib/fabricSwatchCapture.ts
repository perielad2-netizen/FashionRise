/**
 * Capture a high-quality textile reference swatch from the actual Studio fabric
 * tile (built-in or uploaded). Used as Magic images.edit image #2.
 *
 * Only the dominant *garment-scale* patterned fill is sent. Tiny accessory
 * fills (shoes, bags, belts) must not become a global textile for Magic —
 * otherwise ink-painted dress colors get replaced by shoe satin.
 *
 * Multi-fabric sketches are not blocked: the full sketch already carries every
 * painted textile. The optional swatch is a fidelity hint for the main garment
 * fabric — if encoding cannot stay under the transport budget, Magic continues
 * without a swatch (never fails with a size error).
 */
import { getCachedFabricImage, ensureFabricAssetsForFills } from '@/lib/fabricAssetCache'
import { getFabricPromptShort } from '@/lib/fabricPromptCache'
import type { FillOp } from '@/lib/fills'
import {
  BUILTIN_FABRIC_TILE_PX,
  renderFabricTile,
  renderUploadedFabricTile,
} from '@/lib/paintFills'
import { DESIGN_HEIGHT, DESIGN_WIDTH } from '@/lib/strokes'

/** Preferred swatch edge (px). Large enough to show repeat; shrunk only if needed. */
export const FABRIC_SWATCH_EDGE_PX = 512
/**
 * Soft transport budget for the encoded data URL (~1.4MB decoded).
 * Matches backend fabric-swatch validation (sketch upload ceiling).
 * Never fail Magic for size — compress / shrink, then omit if still over.
 */
export const FABRIC_SWATCH_MAX_DATA_URL_CHARS = 1_900_000

const SWATCH_EDGE_STEPS = [512, 384, 256, 192] as const
const JPEG_QUALITY_STEPS = [0.92, 0.85, 0.75, 0.65] as const

/**
 * Patterned fill must cover at least this fraction of the design plane to count
 * as the main garment textile for Magic. Shoes / trims typically sit well below.
 */
export const MAGIC_FABRIC_MIN_DESIGN_AREA_FRACTION = 0.06

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

/** Absolute shoelace area of a closed contour in design pixels. */
export function contourArea(contour: number[]): number {
  const n = Math.floor(contour.length / 2)
  if (n < 3) return 0
  let sum = 0
  for (let i = 0; i < n; i++) {
    const x1 = contour[i * 2]!
    const y1 = contour[i * 2 + 1]!
    const j = (i + 1) % n
    const x2 = contour[j * 2]!
    const y2 = contour[j * 2 + 1]!
    sum += x1 * y2 - x2 * y1
  }
  return Math.abs(sum) / 2
}

/**
 * Prefer the largest patterned fill by contour area (main garment textile),
 * not whatever fill was painted first.
 */
export function dominantPatternedFill(fills: FillOp[]): FillOp | null {
  let best: FillOp | null = null
  let bestArea = 0
  for (const f of fills) {
    if (!isPatternedFill(f)) continue
    const area = contourArea(f.contour)
    if (area > bestArea) {
      best = f
      bestArea = area
    }
  }
  return best
}

/**
 * True when the patterned fill is large enough to be the primary garment fabric
 * (not a shoe / accessory island).
 */
export function isGarmentScalePatternedFill(fill: FillOp): boolean {
  const area = contourArea(fill.contour)
  const plane = DESIGN_WIDTH * DESIGN_HEIGHT
  if (plane <= 0) return false
  return area / plane >= MAGIC_FABRIC_MIN_DESIGN_AREA_FRACTION
}

function tileOntoSwatch(tile: HTMLCanvasElement, edge: number): HTMLCanvasElement {
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

/**
 * Encode a swatch under the transport budget. Prefers PNG, then JPEG quality
 * steps, then smaller edges. Returns null only when every attempt exceeds the
 * budget (Magic then proceeds with the sketch alone — never throws).
 */
export function encodeSwatchDataUrl(
  tile: HTMLCanvasElement,
  maxChars: number = FABRIC_SWATCH_MAX_DATA_URL_CHARS,
): string | null {
  if (!tile.width || !tile.height) return null

  for (const edge of SWATCH_EDGE_STEPS) {
    const swatch = tileOntoSwatch(tile, edge)
    const png = swatch.toDataURL('image/png')
    if (png && png.length <= maxChars) return png

    for (const q of JPEG_QUALITY_STEPS) {
      const jpg = swatch.toDataURL('image/jpeg', q)
      if (jpg && jpg.length <= maxChars) return jpg
    }
  }
  return null
}

/**
 * Build a Magic textile reference from the same tile Studio uses when painting.
 * Returns null when there is no garment-scale patterned fabric, the uploaded
 * asset is unavailable, or the swatch cannot be encoded under budget.
 * Never throws for payload size — multi-fabric Magic must still run.
 */
export async function captureFabricSwatchForMagic(
  fills: FillOp[],
): Promise<FabricSwatchCapture | null> {
  const fill = dominantPatternedFill(fills)
  if (!fill) return null
  if (!isGarmentScalePatternedFill(fill)) return null

  if (fill.style.kind === 'fabric') {
    const tile = renderFabricTile(fill.style.fabricId)
    if (!tile.width || !tile.height) return null
    // Sanity: built-in tiles must match Studio unit size.
    if (tile.width !== BUILTIN_FABRIC_TILE_PX) {
      // Still usable — proceed with whatever renderFabricTile produced.
    }
    const dataUrl = encodeSwatchDataUrl(tile)
    if (!dataUrl) return null
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
    const dataUrl = encodeSwatchDataUrl(tile)
    // Oversized custom textiles: skip swatch rather than block Magic. The
    // sketched multi-fabric look is already in image_base64.
    if (!dataUrl) return null
    const approxBytes = Math.floor((dataUrl.length * 3) / 4)
    const promptShort = getFabricPromptShort(fill.style.assetId)
    const label = promptShort
      ? `${promptShort} repeating textile (exact Studio tile)`
      : 'uploaded fabric repeating textile (exact Studio tile)'
    return {
      dataUrl,
      label,
      kind: 'uploaded-fabric',
      assetId: fill.style.assetId,
      byteLength: approxBytes,
    }
  }

  return null
}
