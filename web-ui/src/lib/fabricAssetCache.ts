import {
  collectUploadedFabricAssetIds,
  type FillOp,
} from '@/lib/fills'
import { fetchFabricImageBlob } from '@/services/fabricAssetsApi'

/** Authenticated owner currently bound to the in-memory fabric caches. */
let activeOwnerId: string | null = null
/** Bumped on every owner change so in-flight responses cannot populate a new account's cache. */
let cacheGeneration = 0

const imageCache = new Map<string, HTMLImageElement>()
const inflight = new Map<string, Promise<HTMLImageElement>>()

/** Optional clear hooks (e.g. uploaded tile cache) — avoids circular imports with paintFills. */
const clearHooks: Array<() => void> = []

export function registerFabricCacheClearHook(hook: () => void): void {
  clearHooks.push(hook)
}

function runClearHooks(): void {
  for (const hook of clearHooks) hook()
}

function cacheKey(ownerId: string, assetId: string): string {
  return `${ownerId.toLowerCase()}:${assetId.toLowerCase()}`
}

export class FabricAssetLoadError extends Error {
  readonly assetId: string
  constructor(assetId: string, message: string) {
    super(message)
    this.name = 'FabricAssetLoadError'
    this.assetId = assetId
  }
}

/**
 * Bind (or clear) fabric image + tile caches to the signed-in user.
 * Call on login, logout, register, and session restore so account switches
 * never reuse another owner's decoded pixels or in-flight fetches.
 */
export function bindFabricCacheToUser(ownerId: string | null): void {
  const next = ownerId?.trim() ? ownerId.trim().toLowerCase() : null
  if (activeOwnerId === next) return
  cacheGeneration += 1
  imageCache.clear()
  inflight.clear()
  runClearHooks()
  activeOwnerId = next
}

export function getFabricCacheOwnerId(): string | null {
  return activeOwnerId
}

export function getCachedFabricImage(assetId: string): HTMLImageElement | null {
  if (!activeOwnerId) return null
  return imageCache.get(cacheKey(activeOwnerId, assetId)) ?? null
}

export function loadFabricAssetImage(assetId: string): Promise<HTMLImageElement> {
  const owner = activeOwnerId
  if (!owner) {
    return Promise.reject(new FabricAssetLoadError(assetId, 'Sign in to load fabric images.'))
  }

  const id = assetId.toLowerCase()
  const key = cacheKey(owner, id)
  const hit = imageCache.get(key)
  if (hit) return Promise.resolve(hit)

  const pending = inflight.get(key)
  if (pending) return pending

  const generationAtStart = cacheGeneration
  const ownerAtStart = owner

  const task = (async () => {
    try {
      const blob = await fetchFabricImageBlob(id)
      if (cacheGeneration !== generationAtStart || activeOwnerId !== ownerAtStart) {
        throw new FabricAssetLoadError(id, 'Account changed while loading fabric.')
      }
      const url = URL.createObjectURL(blob)
      try {
        const img = await decodeImage(url)
        if (cacheGeneration !== generationAtStart || activeOwnerId !== ownerAtStart) {
          throw new FabricAssetLoadError(id, 'Account changed while loading fabric.')
        }
        imageCache.set(key, img)
        return img
      } finally {
        URL.revokeObjectURL(url)
      }
    } catch (err) {
      if (err instanceof FabricAssetLoadError) throw err
      const message =
        err instanceof Error
          ? err.message
          : 'Could not load fabric image.'
      throw new FabricAssetLoadError(id, message)
    } finally {
      inflight.delete(key)
    }
  })()

  inflight.set(key, task)
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

/** Test helper — clears in-memory fabric image cache and owner binding. */
export function __resetFabricAssetCacheForTests(): void {
  cacheGeneration += 1
  imageCache.clear()
  inflight.clear()
  activeOwnerId = null
  runClearHooks()
}
