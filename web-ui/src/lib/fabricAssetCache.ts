import {
  collectUploadedFabricAssetIds,
  type FillOp,
} from '@/lib/fills'
import { fetchFabricImageBlob } from '@/services/fabricAssetsApi'

const imageCache = new Map<string, HTMLImageElement>()
const inflight = new Map<string, Promise<HTMLImageElement>>()

export class FabricAssetLoadError extends Error {
  readonly assetId: string
  constructor(assetId: string, message: string) {
    super(message)
    this.name = 'FabricAssetLoadError'
    this.assetId = assetId
  }
}

export function getCachedFabricImage(assetId: string): HTMLImageElement | null {
  return imageCache.get(assetId.toLowerCase()) ?? null
}

export function loadFabricAssetImage(assetId: string): Promise<HTMLImageElement> {
  const id = assetId.toLowerCase()
  const hit = imageCache.get(id)
  if (hit) return Promise.resolve(hit)

  const pending = inflight.get(id)
  if (pending) return pending

  const task = (async () => {
    try {
      const blob = await fetchFabricImageBlob(id)
      const url = URL.createObjectURL(blob)
      try {
        const img = await decodeImage(url)
        imageCache.set(id, img)
        return img
      } finally {
        URL.revokeObjectURL(url)
      }
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : 'Could not load fabric image.'
      throw new FabricAssetLoadError(id, message)
    } finally {
      inflight.delete(id)
    }
  })()

  inflight.set(id, task)
  return task
}

function decodeImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      if (!img.width || !img.height) reject(new Error('Fabric image failed to decode'))
      else resolve(img)
    }
    img.onerror = () => reject(new Error('Fabric image failed to decode'))
    img.src = src
  })
}

export type EnsureFabricOptions = {
  /**
   * When true (export / Magic), missing fabrics throw.
   * When false (live Studio), missing fabrics are skipped so a placeholder can paint.
   */
  required?: boolean
}

/**
 * Prefetch every uploaded-fabric asset referenced by fills into the image cache.
 */
export async function ensureFabricAssetsForFills(
  fills: FillOp[],
  options: EnsureFabricOptions = {},
): Promise<void> {
  const required = options.required ?? false
  const ids = collectUploadedFabricAssetIds(fills)
  if (ids.length === 0) return

  const results = await Promise.allSettled(ids.map((id) => loadFabricAssetImage(id)))
  if (!required) return

  const failed = results.find((r) => r.status === 'rejected')
  if (failed && failed.status === 'rejected') {
    const reason = failed.reason
    if (reason instanceof FabricAssetLoadError) throw reason
    throw new FabricAssetLoadError(
      'unknown',
      reason instanceof Error ? reason.message : 'Could not load a fabric used in this sketch.',
    )
  }
}

/** Test helper — clears in-memory fabric image cache. */
export function __resetFabricAssetCacheForTests(): void {
  imageCache.clear()
  inflight.clear()
}
