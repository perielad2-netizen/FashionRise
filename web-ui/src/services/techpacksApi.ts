import { ApiError, apiRequest, getApiBaseUrl } from '@/services/api/client'
import { tokenStore } from '@/services/auth/tokenStore'

export type MeasuredValue = {
  value: number | string | null
  unit?: string | null
  source: 'empty' | 'designer' | 'estimate' | 'ai' | 'look'
  note?: string | null
}

export type TechpackExport = {
  id: string
  draft_id: string
  filename: string
  byte_size: number
  page_count: number
  revision: number
  status: string
  verification: string
  metadata: Record<string, unknown>
  created_at: string
}

export type TechpackDraft = {
  id: string
  user_id: string
  look_id: string
  design_id: string | null
  title: string
  style_code: string
  revision: number
  status: string
  verification: string
  spec: Record<string, unknown>
  front_job_id: string | null
  back_job_id: string | null
  created_at: string
  updated_at: string
  latest_export: TechpackExport | null
}

export type TechpackListResponse = {
  items: TechpackDraft[]
  total: number
  limit: number
  offset: number
}

export type TechpackUpdate = {
  title?: string
  style_code?: string
  spec?: Record<string, unknown>
  bump_revision?: boolean
}

export async function createTechpackDraft(lookId: string, title?: string): Promise<TechpackDraft> {
  return apiRequest<TechpackDraft>('/techpacks', {
    method: 'POST',
    body: { look_id: lookId, title: title ?? null },
  })
}

export async function listTechpackDrafts(opts: {
  lookId?: string
  limit?: number
  offset?: number
  signal?: AbortSignal
} = {}): Promise<TechpackListResponse> {
  const params = new URLSearchParams()
  if (opts.lookId) params.set('look_id', opts.lookId)
  params.set('limit', String(opts.limit ?? 24))
  params.set('offset', String(opts.offset ?? 0))
  return apiRequest<TechpackListResponse>(`/techpacks?${params.toString()}`, {
    method: 'GET',
    signal: opts.signal,
  })
}

export async function getTechpackDraft(draftId: string, signal?: AbortSignal): Promise<TechpackDraft> {
  return apiRequest<TechpackDraft>(`/techpacks/${draftId}`, { method: 'GET', signal })
}

export async function updateTechpackDraft(
  draftId: string,
  patch: TechpackUpdate,
): Promise<TechpackDraft> {
  return apiRequest<TechpackDraft>(`/techpacks/${draftId}`, {
    method: 'PATCH',
    body: patch,
  })
}

export async function exportTechpackPdf(draftId: string): Promise<TechpackExport> {
  return apiRequest<TechpackExport>(`/techpacks/${draftId}/export`, { method: 'POST' })
}

export async function fetchTechpackPdfBlob(exportId: string, signal?: AbortSignal): Promise<Blob> {
  const headers: Record<string, string> = { Accept: 'application/pdf' }
  const tokens = tokenStore.get()
  if (tokens?.accessToken) {
    headers.Authorization = `Bearer ${tokens.accessToken}`
  }
  let response: Response
  try {
    response = await fetch(`${getApiBaseUrl()}/techpacks/exports/${exportId}/pdf`, {
      method: 'GET',
      headers,
      signal,
    })
  } catch {
    throw new ApiError('Unable to reach FashionRise. Check that the API is running.', 0, null)
  }
  if (!response.ok) {
    throw new ApiError(`PDF request failed (${response.status})`, response.status, null)
  }
  const blob = await response.blob()
  if (!blob.size) throw new ApiError('Techpack PDF was empty', response.status, null)
  return blob
}

/** Open or create the latest draft for a look (reopen-friendly). */
export async function openOrCreateTechpackForLook(
  lookId: string,
  title?: string,
): Promise<TechpackDraft> {
  const existing = await listTechpackDrafts({ lookId, limit: 1 })
  if (existing.items[0]) return existing.items[0]
  return createTechpackDraft(lookId, title)
}
