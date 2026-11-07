import { ApiError, apiRequest, getApiBaseUrl } from '@/services/api/client'
import { tokenStore } from '@/services/auth/tokenStore'

export type GallerySort = 'newest' | 'top_rated' | 'trending' | 'following' | 'circle' | 'top10'

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
  my_score?: number | null
}

export type GalleryRating = {
  id: string
  gallery_item_id: string
  user_id: string
  score: number
  created_at: string
  updated_at: string
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

export async function getGalleryItem(
  id: string,
  signal?: AbortSignal,
): Promise<GalleryItem> {
  return apiRequest<GalleryItem>(`/gallery/${encodeURIComponent(id)}`, {
    method: 'GET',
    signal,
  })
}

export async function likeGalleryItem(id: string): Promise<void> {
  await apiRequest<void>(`/gallery/${encodeURIComponent(id)}/like`, { method: 'POST' })
}

export async function unlikeGalleryItem(id: string): Promise<void> {
  await apiRequest<void>(`/gallery/${encodeURIComponent(id)}/like`, { method: 'DELETE' })
}

export async function rateGalleryItem(id: string, score: number): Promise<GalleryRating> {
  return apiRequest<GalleryRating>('/ratings', {
    method: 'POST',
    body: { gallery_item_id: id, score },
  })
}

export type GalleryComment = {
  id: string
  gallery_item_id: string
  user_id: string
  body: string
  moderation_status: string
  likes_count: number
  created_at: string
  username?: string | null
  liked_by_me?: boolean | null
}

export async function listGalleryComments(
  id: string,
  signal?: AbortSignal,
): Promise<GalleryComment[]> {
  return apiRequest<GalleryComment[]>(`/gallery/${encodeURIComponent(id)}/comments`, {
    method: 'GET',
    signal,
  })
}

export async function postGalleryComment(id: string, body: string): Promise<GalleryComment> {
  return apiRequest<GalleryComment>(`/gallery/${encodeURIComponent(id)}/comments`, {
    method: 'POST',
    body: { body },
  })
}

export async function likeGalleryComment(commentId: string): Promise<void> {
  await apiRequest<void>(`/gallery/comments/${encodeURIComponent(commentId)}/like`, {
    method: 'POST',
  })
}

export async function unlikeGalleryComment(commentId: string): Promise<void> {
  await apiRequest<void>(`/gallery/comments/${encodeURIComponent(commentId)}/like`, {
    method: 'DELETE',
  })
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
