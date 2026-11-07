import { apiRequest } from '@/services/api/client'

export type GallerySort = 'newest' | 'top_rated' | 'trending' | 'following'

export type GalleryItem = {
  id: string
  design_id: string
  user_id: string
  title: string
  image_url: string | null
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
