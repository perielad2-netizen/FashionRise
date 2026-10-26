import { apiRequest } from '@/services/api/client'

export type LookSide = {
  job_id: string
  studio_side: 'front' | 'back' | null
  has_image: boolean
  summary: string | null
  created_at: string
}

export type LookRecord = {
  id: string
  title: string
  is_favorite: boolean
  is_archived: boolean
  kind: 'single' | 'dual'
  created_at: string
  updated_at: string
  front: LookSide | null
  back: LookSide | null
  design_id: string | null
  magic_operation_id: string | null
}

export type LookListResponse = {
  items: LookRecord[]
  total: number
  limit: number
  offset: number
}

export type LookFilter = 'all' | 'favorites' | 'archived'

export type LookUpdate = {
  title?: string
  is_favorite?: boolean
  is_archived?: boolean
}

export async function listLooks(
  opts: {
    filter?: LookFilter
    q?: string
    limit?: number
    offset?: number
    signal?: AbortSignal
  } = {},
): Promise<LookListResponse> {
  const params = new URLSearchParams()
  params.set('filter', opts.filter ?? 'all')
  if (opts.q?.trim()) params.set('q', opts.q.trim())
  params.set('limit', String(opts.limit ?? 24))
  params.set('offset', String(opts.offset ?? 0))
  return apiRequest<LookListResponse>(`/looks?${params.toString()}`, {
    method: 'GET',
    signal: opts.signal,
  })
}

export async function getLook(lookId: string, signal?: AbortSignal): Promise<LookRecord> {
  return apiRequest<LookRecord>(`/looks/${lookId}`, { method: 'GET', signal })
}

export async function updateLook(lookId: string, patch: LookUpdate): Promise<LookRecord> {
  return apiRequest<LookRecord>(`/looks/${lookId}`, {
    method: 'PATCH',
    body: patch,
  })
}

/** Primary image job for gallery thumbnails (front preferred). */
export function lookThumbnailJobId(look: LookRecord): string | null {
  if (look.front?.has_image) return look.front.job_id
  if (look.back?.has_image) return look.back.job_id
  return null
}
