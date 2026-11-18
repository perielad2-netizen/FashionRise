/**
 * Broadcast the signed-in user's avatar URL so GlobalHeader (and peers) update
 * immediately after Change photo — without remounting the whole shell.
 */

type Listener = (avatarUrl: string | null) => void

let currentAvatarUrl: string | null = null
let currentUserId: string | null = null
const listeners = new Set<Listener>()

export function publishMyProfileAvatar(userId: string, avatarUrl: string | null): void {
  currentUserId = userId
  currentAvatarUrl = avatarUrl
  for (const listener of listeners) listener(avatarUrl)
}

export function peekMyProfileAvatar(): { userId: string | null; avatarUrl: string | null } {
  return { userId: currentUserId, avatarUrl: currentAvatarUrl }
}

export function subscribeMyProfileAvatar(listener: Listener): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/** Test-only. */
export const __myProfileAvatarStoreTestUtils = {
  clear() {
    currentAvatarUrl = null
    currentUserId = null
    listeners.clear()
  },
}
