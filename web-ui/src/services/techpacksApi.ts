import { ApiError, apiRequest, getApiBaseUrl } from '@/services/api/client'
import { tokenStore } from '@/services/auth/tokenStore'

export type MeasuredValueSource =
  | 'empty'
  | 'designer'
  | 'estimate'
  | 'ai'
  | 'look'
  | 'calculated'
  | 'unknown'

export type MeasuredValue = {
  value: number | string | null
  unit?: string | null
  source: MeasuredValueSource
  note?: string | null
  definition?: string | null
  confidence?: string | null
  review_status?: string | null
  assumptions?: string[]
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

export type TechpackPieceCategory =
  | 'dress'
  | 'shirt'
  | 'top'
  | 'jacket'
  | 'skirt'
  | 'trousers'
  | 'shorts'
  | 'jumpsuit'
  | 'set'
  | 'other'

export type TechpackPiece = {
  id: string
  category: TechpackPieceCategory | string
  label: string
  role?: string
  color_hint?: string
  detection_source?: string
  materials?: {
    shell?: {
      name?: string
      suggestion?: string
      composition?: string
      source?: string
    }
    lining?: { name?: string; source?: string }
    interfacing?: { name?: string; source?: string }
  }
  closures?: {
    type?: string
    suggestion?: string
    notes?: string
    source?: string
  }
  fit?: {
    silhouette?: string
    suggestion?: string
    ease_note?: string
  }
  finished_measurements?: Record<string, MeasuredValue>
  bom?: unknown[]
  pattern_pieces?: unknown[]
  construction_steps?: unknown[]
  illustrations?: Record<string, unknown>
  [key: string]: unknown
}

export type TechpackOutfit = {
  piece_count: number
  pieces: TechpackPiece[]
  detection_confidence?: string
  needs_user_confirm?: boolean
  note?: string
}

export type TechpackSpecV2 = {
  schema_version: string
  workflow_stage?: 'understand' | 'customize' | 'measurements' | 'generate' | string
  units?: string
  size_system?: string
  sample_size?: string
  quantity?: number | null
  look_notes?: string
  designer_notes?: string
  disclaimer?: string
  outfit?: TechpackOutfit
  body?: Record<string, MeasuredValue>
  preferences?: {
    fit_preference?: string
    notes?: string
  }
  warnings?: Array<Record<string, unknown> | string>
  qc_checklist?: Array<{ item: string; checked: boolean }>
  ai?: {
    last_run_id?: string | null
    last_mode?: string
    paid_sections?: string[]
    estimated_cost_usd_cents?: number | null
    actual_cost_usd_cents?: number | null
    vision_model?: string | null
    image_model?: string | null
    analysis_summary?: string | null
  }
  [key: string]: unknown
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
  spec: TechpackSpecV2 | Record<string, unknown>
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

export type TechpackAiMode = 'heuristic' | 'ai' | 'professional'

export type TechpackAiStatus = {
  enabled: boolean
  configured_flag?: boolean
  api_key_present?: boolean
  spend_ceiling_usd?: number
  max_usd_per_run?: number
  max_usd_per_user_day?: number
  estimate_chat_cents?: number
  estimate_professional_cents_min?: number
  estimate_professional_cents_max?: number
  professional_available?: boolean
  owner_allowlisted?: boolean
  requires_entitlement?: boolean
  model?: string | null
  vision_model?: string | null
  image_model?: string | null
  note?: string
}

export type TechpackAiConfirmResponse = {
  draft_id: string
  stage: string
  confirm_token: string
  estimated_cost_usd_cents: number
  ai_enabled: boolean
  model?: string | null
  message: string
  expires_hint_seconds?: number
  max_usd_per_run?: number
  mode?: TechpackAiMode | string
}

export type TechpackArtifact = {
  id: string
  piece_id?: string | null
  kind: string
  url_path?: string | null
  review_state?: string | null
}

export type TechpackAiGenerateRequest = {
  confirm_token: string
  idempotency_key: string
  mode: TechpackAiMode
  sections?: string[]
  propose_back?: boolean
}

export type TechpackAiGenerateResponse = {
  run_id: string
  status: string
  cost_usd_cents: number
  mode: string
  draft_id?: string
  warnings?: Array<Record<string, unknown> | string>
  result?: Record<string, unknown> | null
  idempotent_replay?: boolean
  artifacts?: TechpackArtifact[]
  estimated_cost_usd_cents?: number
  actual_cost_usd_cents?: number
  analysis_summary?: string | null
  failed_sections?: string[]
}

export type TechpackAiProgress = {
  phase?: string
  message?: string
  piece_id?: string | null
  detail?: string | null
  pieces_done?: number
  pieces_total?: number
}

export type TechpackAiRun = {
  id: string
  draft_id: string
  stage: string
  status: string
  model?: string | null
  cost_usd_cents: number
  result?: Record<string, unknown> | null
  error_message?: string | null
  created_at?: string | null
  progress?: TechpackAiProgress | null
  artifacts?: TechpackArtifact[]
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

export async function getTechpackAiStatus(signal?: AbortSignal): Promise<TechpackAiStatus> {
  return apiRequest<TechpackAiStatus>('/techpacks/ai/status', { method: 'GET', signal })
}

export async function confirmTechpackAi(
  draftId: string,
  stage: string,
  mode?: TechpackAiMode,
): Promise<TechpackAiConfirmResponse> {
  return apiRequest<TechpackAiConfirmResponse>(`/techpacks/${draftId}/ai/confirm`, {
    method: 'POST',
    body: mode ? { stage, mode } : { stage },
  })
}

export async function generateTechpackAi(
  draftId: string,
  body: TechpackAiGenerateRequest,
): Promise<TechpackAiGenerateResponse> {
  return apiRequest<TechpackAiGenerateResponse>(`/techpacks/${draftId}/ai/generate`, {
    method: 'POST',
    body,
  })
}

/** One-tap Professional — server mints spend-gated intent; user click is authorization. */
export async function generateTechpackAiProfessionalOneTap(
  draftId: string,
  body: { idempotency_key: string; propose_back?: boolean; sections?: string[] },
): Promise<TechpackAiGenerateResponse> {
  return apiRequest<TechpackAiGenerateResponse>(
    `/techpacks/${draftId}/ai/generate-professional`,
    {
      method: 'POST',
      body,
    },
  )
}

export async function getTechpackAiRun(
  runId: string,
  signal?: AbortSignal,
): Promise<TechpackAiRun> {
  return apiRequest<TechpackAiRun>(`/techpacks/ai/runs/${runId}`, { method: 'GET', signal })
}

export async function getLatestTechpackAiRun(
  draftId: string,
  signal?: AbortSignal,
): Promise<TechpackAiRun | null> {
  const row = await apiRequest<TechpackAiRun | { status?: string; run?: null }>(
    `/techpacks/${draftId}/ai/latest-run`,
    { method: 'GET', signal },
  )
  if (!row || typeof row !== 'object') return null
  if ('id' in row && typeof (row as TechpackAiRun).id === 'string') return row as TechpackAiRun
  return null
}

/** Authenticated technical-illustration image for a generate artifact. */
export async function fetchTechpackArtifactBlob(
  artifactId: string,
  signal?: AbortSignal,
): Promise<Blob> {
  const headers: Record<string, string> = { Accept: 'image/*' }
  const tokens = tokenStore.get()
  if (tokens?.accessToken) {
    headers.Authorization = `Bearer ${tokens.accessToken}`
  }
  let response: Response
  try {
    response = await fetch(`${getApiBaseUrl()}/techpacks/artifacts/${artifactId}/image`, {
      method: 'GET',
      headers,
      signal,
    })
  } catch {
    throw new ApiError('Unable to reach FashionRise. Check that the API is running.', 0, null)
  }
  if (!response.ok) {
    throw new ApiError(`Artifact image request failed (${response.status})`, response.status, null)
  }
  const blob = await response.blob()
  if (!blob.size) throw new ApiError('Techpack artifact image was empty', response.status, null)
  return blob
}
