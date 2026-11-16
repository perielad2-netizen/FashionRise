/**
 * Session Follow cache shared by FashionRise feed cards and designer profiles.
 * Profile Follow/Unfollow must publish here so remounted feed cards stay in sync.
 */

const followStatusCache = new Map<string, boolean>()
const followStatusListeners = new Map<string, Set<(following: boolean) => void>>()

export function followStatusCacheKey(viewerId: string, designerId: string): string {
  return `${viewerId}:${designerId}`
}

export function publishFollowStatus(cacheKey: string, following: boolean): void {
  followStatusCache.set(cacheKey, following)
  const listeners = followStatusListeners.get(cacheKey)
  if (!listeners) return
  for (const listener of listeners) listener(following)
}

/** Publish by viewer + designer ids (profile / feed toggles). */
export function syncFollowStatus(
  viewerId: string,
  designerId: string,
  following: boolean,
): void {
  publishFollowStatus(followStatusCacheKey(viewerId, designerId), following)
}

export function subscribeFollowStatus(
  cacheKey: string,
  listener: (following: boolean) => void,
): () => void {
  let bucket = followStatusListeners.get(cacheKey)
  if (!bucket) {
    bucket = new Set()
    followStatusListeners.set(cacheKey, bucket)
  }
  bucket.add(listener)
  return () => {
    bucket?.delete(listener)
    if (bucket && bucket.size === 0) followStatusListeners.delete(cacheKey)
  }
}

export function peekFollowStatus(cacheKey: string): boolean | undefined {
  return followStatusCache.get(cacheKey)
}

/**
 * Apply a server Follow status. Always trusts the latest fetch so a profile
 * Follow is not stuck behind a stale first-card `false`.
 */
export function applyFetchedFollowStatus(cacheKey: string, following: boolean): boolean {
  publishFollowStatus(cacheKey, following)
  return following
}

/** Test-only helpers. */
export const __followStatusCacheTestUtils = {
  clear() {
    followStatusCache.clear()
    followStatusListeners.clear()
  },
  set(viewerId: string, designerId: string, following: boolean) {
    syncFollowStatus(viewerId, designerId, following)
  },
  get(viewerId: string, designerId: string): boolean | undefined {
    return followStatusCache.get(followStatusCacheKey(viewerId, designerId))
  },
  size() {
    return followStatusCache.size
  },
}
