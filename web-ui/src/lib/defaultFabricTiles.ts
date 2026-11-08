import { FABRIC_PRESETS } from '@/lib/fills'

const imageCache = new Map<string, HTMLImageElement>()
const inflight = new Map<string, Promise<HTMLImageElement>>()
let preloadPromise: Promise<void> | null = null

function decodeImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.decoding = 'async'
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error(`Failed to load fabric tile ${url}`))
    img.src = url
  })
}

/** Sync lookup for paint/export once a default tile has been decoded. */
export function getCachedDefaultFabricImage(fabricId: string): HTMLImageElement | null {
  return imageCache.get(fabricId) ?? null
}

export function loadDefaultFabricImage(fabricId: string): Promise<HTMLImageElement> {
  const preset = FABRIC_PRESETS.find((p) => p.id === fabricId && p.tileUrl)
  if (!preset?.tileUrl) {
    return Promise.reject(new Error(`No default tile for fabric ${fabricId}`))
  }
  const hit = imageCache.get(fabricId)
  if (hit) return Promise.resolve(hit)
  const pending = inflight.get(fabricId)
  if (pending) return pending

  const task = decodeImage(preset.tileUrl)
    .then((img) => {
      imageCache.set(fabricId, img)
      return img
    })
    .finally(() => {
      inflight.delete(fabricId)
    })
  inflight.set(fabricId, task)
  return task
}

/** Prefetch every image-backed default fabric (idempotent). */
export function preloadDefaultFabricTiles(): Promise<void> {
  if (preloadPromise) return preloadPromise
  const ids = FABRIC_PRESETS.filter((p) => p.tileUrl).map((p) => p.id)
  preloadPromise = Promise.allSettled(ids.map((id) => loadDefaultFabricImage(id))).then(() => undefined)
  return preloadPromise
}

export function defaultFabricTileIds(): string[] {
  return FABRIC_PRESETS.filter((p) => p.tileUrl).map((p) => p.id)
}
