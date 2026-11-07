import { ApiError, apiRequest, getApiBaseUrl } from '@/services/api/client'
import { tokenStore } from '@/services/auth/tokenStore'

export type GallerySort = 'newest' | 'top_rated' | 'trending' | 'following'

export type GalleryItem = {
  id: string
  design_id: string | null
  look_id: string | null
  user_id: string
  title: string
  image_url: string | null
  image_path?: string | null
  visibility: string
  rating_average: number | null
  rating_count: number
  likes_count: number
  moderation_status: string
  created_at: string
  updated_at: string
  liked_by_me?: boolean | null
}

export async function listGallery(opts?: {
  sort?: GallerySort
  limit?: number
  offset?: number
  signal?: AbortSignal
}): Promise<GalleryItem[]> {
  const sort = opts?.sort ?? 'newest'
  const limit = opts?.limit ?? 24
  const offset = opts?.offset ?? 0
  const q = new URLSearchParams({
    sort,
    limit: String(limit),
    offset: String(offset),
  })
  return apiRequest<GalleryItem[]>(`/gallery?${q.toString()}`, {
    method: 'GET',
    signal: opts?.signal,
  })
}

export async function likeGalleryItem(id: string): Promise<void> {
  await apiRequest<void>(`/gallery/${encodeURIComponent(id)}/like`, { method: 'POST' })
}

export async function unlikeGalleryItem(id: string): Promise<void> {
  await apiRequest<void>(`/gallery/${encodeURIComponent(id)}/like`, { method: 'DELETE' })
}

/** Authenticated Runway thumbnail bytes for a published gallery item. */
export async function fetchGalleryImageBlob(
  galleryItemId: string,
  signal?: AbortSignal,
): Promise<Blob> {
  const headers: Record<string, string> = { Accept: 'image/*,application/octet-stream' }
  const tokens = tokenStore.get()
  if (tokens?.accessToken) {
    headers.Authorization = `Bearer ${tokens.accessToken}`
  }
  let response: Response
  try {
    response = await fetch(`${getApiBaseUrl()}/gallery/${encodeURIComponent(galleryItemId)}/image`, {
      method: 'GET',
      headers,
      signal,
    })
  } catch {
    throw new ApiError('Unable to reach FashionRise. Check that the API is running.', 0, null)
  }
  if (!response.ok) {
    throw new ApiError('Could not load Runway image', response.status, null)
  }
  return response.blob()
}
