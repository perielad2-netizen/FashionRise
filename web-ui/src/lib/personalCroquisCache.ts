/**
 * Owner-bound object-URL cache for personal croquis generated assets.
 * Entries are keyed by exact (userId, croquisId, version, assetId) so a slow
 * fetch for pin A cannot paint under pin B.
 */

import { fetchCroquisAssetBlob } from '@/services/personalCroquisApi'

export type PersonalCroquisUnderlayIdentity = {
  userId: string
  croquisId: string
  version: number
  assetId: string
}

export function underlayIdentityKey(id: PersonalCroquisUnderlayIdentity): string {
  return `${id.userId}|${id.croquisId}|${id.version}|${id.assetId}`
}

/** True only when a loaded underlay identity is exactly the current Studio pin. */
export function underlayMatchesPin(
  identity: PersonalCroquisUnderlayIdentity | null | undefined,
  pin: {
    userId?: string | null
    croquisId?: string | null
    version?: number | null
  },
): boolean {
  if (!identity || !pin.userId || !pin.croquisId || pin.version == null) return false
  return (
    identity.userId === pin.userId &&
    identity.croquisId === pin.croquisId &&
    identity.version === pin.version
  )
}

type CacheEntry = {
  identity: PersonalCroquisUnderlayIdentity
  objectUrl: string
}

let boundUserId: string | null = null
const byKey = new Map<string, CacheEntry>()
const inflight = new Map<string, Promise<string>>()

export function bindPersonalCroquisCacheToUser(userId: string | null): void {
  if (boundUserId === userId) return
  for (const entry of byKey.values()) {
    URL.revokeObjectURL(entry.objectUrl)
  }
  byKey.clear()
  inflight.clear()
  boundUserId = userId
}

export function peekPersonalCroquisObjectUrl(
  identity: PersonalCroquisUnderlayIdentity,
): string | null {
  if (boundUserId && identity.userId !== boundUserId) return null
  return byKey.get(underlayIdentityKey(identity))?.objectUrl ?? null
}

export async function loadPersonalCroquisObjectUrl(
  identity: PersonalCroquisUnderlayIdentity,
  signal?: AbortSignal,
): Promise<string> {
  if (!identity.userId) throw new Error('userId required for personal croquis cache')
  if (boundUserId !== identity.userId) bindPersonalCroquisCacheToUser(identity.userId)

  const key = underlayIdentityKey(identity)
  const existing = byKey.get(key)
  if (existing) return existing.objectUrl

  const pending = inflight.get(key)
  if (pending) return pending

  const task = (async () => {
    const blob = await fetchCroquisAssetBlob(identity.assetId, signal)
    if (boundUserId !== identity.userId) {
      throw new Error('personal croquis cache user changed during fetch')
    }
    const objectUrl = URL.createObjectURL(blob)
    const prev = byKey.get(key)
    if (prev) URL.revokeObjectURL(prev.objectUrl)
    byKey.set(key, { identity: { ...identity }, objectUrl })
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
