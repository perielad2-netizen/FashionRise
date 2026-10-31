/**
 * Owner-bound object-URL cache for personal croquis generated assets.
 * Mirrors fabricAssetCache: revoke on user switch; never use public static URLs.
 */

import { fetchCroquisAssetBlob } from '@/services/personalCroquisApi'

type CacheEntry = {
  userId: string
  assetId: string
  objectUrl: string
}

let boundUserId: string | null = null
const byAsset = new Map<string, CacheEntry>()
const inflight = new Map<string, Promise<string>>()

export function bindPersonalCroquisCacheToUser(userId: string | null): void {
  if (boundUserId === userId) return
  for (const entry of byAsset.values()) {
    URL.revokeObjectURL(entry.objectUrl)
  }
  byAsset.clear()
  inflight.clear()
  boundUserId = userId
}

export function peekPersonalCroquisObjectUrl(assetId: string): string | null {
  const entry = byAsset.get(assetId)
  if (!entry) return null
  if (boundUserId && entry.userId !== boundUserId) return null
  return entry.objectUrl
}

export async function loadPersonalCroquisObjectUrl(
  userId: string,
  assetId: string,
  signal?: AbortSignal,
): Promise<string> {
  if (!userId) throw new Error('userId required for personal croquis cache')
  if (boundUserId !== userId) bindPersonalCroquisCacheToUser(userId)

  const existing = byAsset.get(assetId)
  if (existing && existing.userId === userId) return existing.objectUrl

  const key = `${userId}:${assetId}`
  const pending = inflight.get(key)
  if (pending) return pending

  const task = (async () => {
    const blob = await fetchCroquisAssetBlob(assetId, signal)
    if (boundUserId !== userId) {
      throw new Error('personal croquis cache user changed during fetch')
    }
    const objectUrl = URL.createObjectURL(blob)
    const prev = byAsset.get(assetId)
    if (prev) URL.revokeObjectURL(prev.objectUrl)
    byAsset.set(assetId, { userId, assetId, objectUrl })
    return objectUrl
  })()

  inflight.set(key, task)
  try {
    return await task
  } finally {
    inflight.delete(key)
  }
}

export function clearPersonalCroquisCache(): void {
  bindPersonalCroquisCacheToUser(null)
}
