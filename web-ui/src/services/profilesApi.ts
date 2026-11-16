import { apiRequest } from '@/services/api/client'

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
  return apiRequest<PublicProfile>('/profiles/me', {
    method: 'PUT',
    body: JSON.stringify(payload),
    signal,
  })
}
