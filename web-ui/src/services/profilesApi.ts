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
  /** Prefer counting published Runway looks from listUserGallery instead of this field. */
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

export async function getPublicProfile(
  userId: string,
  signal?: AbortSignal,
): Promise<PublicProfile> {
  return apiRequest<PublicProfile>(`/profiles/${encodeURIComponent(userId)}`, {
    method: 'GET',
    signal,
  })
}
