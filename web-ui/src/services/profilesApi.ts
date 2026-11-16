import { ApiError, apiRequest, getApiBaseUrl } from '@/services/api/client'
import { tokenStore } from '@/services/auth/tokenStore'

/**
 * Public profile fields from GET /profiles/{user_id}.
 * Do not surface private account fields (email, etc.) — the API does not return them.
 */
export type PublicProfile = {
  id: string
  user_id: string
  display_name: string
  bio: string | null
  avatar_url: string | null
  cover_url: string | null
  style_tags: unknown[]
  /** Prefer counting published FashionRise looks from listUserGallery instead of this field. */
  published_count: number
  followers_count: number
  likes_received_count: number
  rating_average: number | null
  rating_count: number
  reputation_score: number
  reputation_tier: string
  created_at: string
  updated_at: string
  /** Intentionally unused in friend UI — may include private design counts. */
  designs_count?: number
}

export type FollowStatus = {
  user_id: string
  following: boolean
}

export type FollowerListItem = {
  user_id: string
  username: string
  display_name?: string | null
  avatar_url?: string | null
  following: boolean
}

export async function getPublicProfile(
  userId: string,
  signal?: AbortSignal,
): Promise<PublicProfile> {
  return apiRequest<PublicProfile>(`/profiles/${encodeURIComponent(userId)}`, {
    method: 'GET',
    signal,
  })
}

export async function getFollowStatus(
  userId: string,
  signal?: AbortSignal,
): Promise<FollowStatus> {
  return apiRequest<FollowStatus>(
    `/profiles/${encodeURIComponent(userId)}/follow-status`,
    { method: 'GET', signal },
  )
}

export async function followCreator(userId: string, signal?: AbortSignal): Promise<void> {
  await apiRequest<void>(`/profiles/${encodeURIComponent(userId)}/follow`, {
    method: 'POST',
    signal,
  })
}

export async function unfollowCreator(userId: string, signal?: AbortSignal): Promise<void> {
  await apiRequest<void>(`/profiles/${encodeURIComponent(userId)}/follow`, {
    method: 'DELETE',
    signal,
  })
}

export async function listProfileFollowers(
  userId: string,
  opts?: { limit?: number; offset?: number; signal?: AbortSignal },
): Promise<FollowerListItem[]> {
  const q = new URLSearchParams({
    limit: String(opts?.limit ?? 50),
    offset: String(opts?.offset ?? 0),
  })
  return apiRequest<FollowerListItem[]>(
    `/profiles/${encodeURIComponent(userId)}/followers?${q}`,
    { method: 'GET', signal: opts?.signal },
  )
}

export async function listProfileFollowing(
  userId: string,
  opts?: { limit?: number; offset?: number; signal?: AbortSignal },
): Promise<FollowerListItem[]> {
  const q = new URLSearchParams({
    limit: String(opts?.limit ?? 50),
    offset: String(opts?.offset ?? 0),
  })
  return apiRequest<FollowerListItem[]>(
    `/profiles/${encodeURIComponent(userId)}/following?${q}`,
    { method: 'GET', signal: opts?.signal },
  )
}

export type ProfileUpdatePayload = {
  display_name?: string
  bio?: string | null
  avatar_url?: string | null
  cover_url?: string | null
  style_tags?: string[]
}

export async function getMyProfile(signal?: AbortSignal): Promise<PublicProfile> {
  return apiRequest<PublicProfile>('/profiles/me', { method: 'GET', signal })
}

export async function updateMyProfile(
  payload: ProfileUpdatePayload,
  signal?: AbortSignal,
): Promise<PublicProfile> {
  // Pass the object — apiRequest / authorizedFetch JSON.stringify once.
  // Double-stringify sent a JSON string body → Pydantic 422
  // "Input should be a valid dictionary or object to extract fields from"
  // (Android Edit Designer Card Save after a successful photo upload).
  return apiRequest<PublicProfile>('/profiles/me', {
    method: 'PUT',
    body: payload,
    signal,
  })
}

/**
 * When the API base is absolute (Capacitor native), relative `/api/...` and
 * `/static/...` avatar paths must be rewritten onto the FashionRise origin —
 * otherwise `<img>` resolves against `https://localhost` and breaks.
 */
function absolutizePublicAssetPath(path: string): string {
  if (
    path.startsWith('blob:') ||
    path.startsWith('http://') ||
    path.startsWith('https://') ||
    path.startsWith('data:')
  ) {
    return path
  }
  try {
    const apiBase = getApiBaseUrl()
    if (!apiBase.startsWith('http')) return path
    const origin = new URL(apiBase).origin
    if (path.startsWith('/')) return `${origin}${path}`
    return `${origin}/${path.replace(/^\/+/, '')}`
  } catch {
    return path
  }
}

/**
 * Resolve an `<img src>` for a designer photo.
 *
 * - Legacy `/static/uploads/...` values stay as-is (do not rewrite to the private
 *   avatar route — that file may not exist there).
 * - New private-avatar uploads use `/api/v1/profiles/{id}/avatar`.
 * - Absolute API bases (Android/iOS shells) get same-origin absolute URLs.
 */
export function profileAvatarSrc(
  userId: string,
  avatarUrl: string | null | undefined,
  cacheKey?: string | null,
): string | null {
  if (!avatarUrl) return null

  let base: string
  if (avatarUrl.includes('/static/uploads/')) {
    // Preserve earlier upload workflow URLs.
    base =
      avatarUrl.startsWith('http') || avatarUrl.startsWith('/')
        ? avatarUrl
        : `/${avatarUrl.replace(/^\/+/, '')}`
  } else if (avatarUrl.includes('/profiles/') && avatarUrl.includes('/avatar')) {
    base = `/api/v1/profiles/${encodeURIComponent(userId)}/avatar`
  } else if (
    avatarUrl.startsWith('http') ||
    avatarUrl.startsWith('/') ||
    avatarUrl.startsWith('blob:')
  ) {
    base = avatarUrl
  } else {
    // Unknown relative marker from the new private-avatar flow.
    base = `/api/v1/profiles/${encodeURIComponent(userId)}/avatar`
  }

  base = absolutizePublicAssetPath(base)

  if (!cacheKey || base.startsWith('blob:')) return base
  const join = base.includes('?') ? '&' : '?'
  return `${base}${join}v=${encodeURIComponent(cacheKey)}`
}

export async function uploadMyAvatar(
  file: File,
  signal?: AbortSignal,
): Promise<PublicProfile> {
  const tokens = tokenStore.get()
  if (!tokens?.accessToken) {
    throw new ApiError('Sign in required to update your photo.', 401, null)
  }

  const form = new FormData()
  form.append('file', file, file.name || 'avatar.jpg')

  let response: Response
  try {
    response = await fetch(`${getApiBaseUrl()}/profiles/me/avatar`, {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${tokens.accessToken}`,
      },
      body: form,
      signal,
    })
  } catch {
    throw new ApiError('Unable to reach FashionRise. Check that the API is running.', 0, null)
  }

  const text = await response.text()
  let parsed: unknown = null
  if (text) {
    try {
      parsed = JSON.parse(text)
    } catch {
      parsed = text
    }
  }

  if (!response.ok) {
    const detail =
      typeof parsed === 'object' &&
      parsed !== null &&
      'detail' in parsed &&
      typeof (parsed as { detail: unknown }).detail === 'string'
        ? (parsed as { detail: string }).detail
        : 'Could not update photo'
    throw new ApiError(detail, response.status, parsed)
  }

  return parsed as PublicProfile
}
