import { ApiError, apiRequest, getApiBaseUrl } from '@/services/api/client'
import { tokenStore } from '@/services/auth/tokenStore'
import type { AiJobRead } from '@/services/ai/aiJobTypes'
import type { SharedGarmentSpec } from '@/services/ai/magicGarmentSpec'

/** BE `content_fingerprint` max_length=128 — draft JSON fingerprints must be digested. */
const CONTENT_FINGERPRINT_MAX = 128

/**
 * Map a Studio draft fingerprint to the API wire form.
 * Short values (tests / already-hashed digests) pass through; longer JSON payloads
 * become SHA-256 hex (64 chars) so Dual Magic enqueue does not 422.
 */
export async function toApiContentFingerprint(
  value?: string | null,
): Promise<string | null> {
  if (value == null) return null
  const trimmed = value.trim()
  if (!trimmed) return null
  if (trimmed.length <= CONTENT_FINGERPRINT_MAX) return trimmed
  const data = new TextEncoder().encode(trimmed)
  const digest = await crypto.subtle.digest('SHA-256', data)
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('')
}

export type PolishSidePayload = {
  image_base64: string
  /**
   * Optional PNG data URL of the exact Studio fabric tile (patterned fills only).
   * Sent as images.edit image #2; never invent for solids/gradients.
   */
  fabric_swatch_base64?: string
  notes?: string
  /** Required for dual polish — unique per side within an operation. */
  idempotency_key: string
}

export type PolishSketchDualInput = {
  design_id?: string | null
  /** Required — stable client operation UUID shared by both jobs. */
  magic_operation_id: string
  reference_model_id?: string
  notes?: string
  mood_notes?: string
  /** Required — bounded shared garment context for Front/Back coordination. */
  shared_garment_spec: SharedGarmentSpec
  /** Immutable document revision (maps to BE `source_revision`). */
  source_revision?: number
  /** Immutable content fingerprint (maps to BE `content_fingerprint`). */
  content_fingerprint?: string
  front: PolishSidePayload
  back: PolishSidePayload
  signal?: AbortSignal
}

export type SketchPolishDualRead = {
  magic_operation_id: string
  front_job: AiJobRead
  back_job: AiJobRead
}

export type PolishSketchInput = {
  imageBase64: string
  /** Optional exact Studio fabric tile PNG data URL (patterned fills). */
  fabricSwatchBase64?: string
  notes?: string
  designId?: string | null
  /** WEB-V4J dual-sided polish grouping. */
  magic_operation_id?: string
  studio_side?: 'front' | 'back'
  reference_model_id?: string
  /** Required for linked Front/Back attempts (incl. failed-side retry). */
  idempotency_key?: string
  shared_garment_spec?: SharedGarmentSpec
  source_revision?: number
  content_fingerprint?: string
  signal?: AbortSignal
}

export async function enqueueSketchPolishDual(
  input: PolishSketchDualInput,
): Promise<SketchPolishDualRead> {
  const contentFingerprint = await toApiContentFingerprint(input.content_fingerprint)
  return apiRequest<SketchPolishDualRead>('/ai/sketch/polish-dual', {
    method: 'POST',
    body: {
      design_id: input.design_id ?? null,
      magic_operation_id: input.magic_operation_id,
      reference_model_id: input.reference_model_id ?? null,
      notes: input.notes ?? 'polish concept',
      mood_notes: input.mood_notes,
      shared_garment_spec: input.shared_garment_spec,
      source_revision: input.source_revision ?? null,
      content_fingerprint: contentFingerprint,
      front: {
        image_base64: input.front.image_base64,
        ...(input.front.fabric_swatch_base64
          ? { fabric_swatch_base64: input.front.fabric_swatch_base64 }
          : {}),
        notes: input.front.notes,
        idempotency_key: input.front.idempotency_key,
      },
      back: {
        image_base64: input.back.image_base64,
        ...(input.back.fabric_swatch_base64
          ? { fabric_swatch_base64: input.back.fabric_swatch_base64 }
          : {}),
        notes: input.back.notes,
        idempotency_key: input.back.idempotency_key,
      },
    },
    signal: input.signal,
  })
}

export async function enqueueSketchPolish(input: PolishSketchInput): Promise<AiJobRead> {
  const contentFingerprint = await toApiContentFingerprint(input.content_fingerprint)
  return apiRequest<AiJobRead>('/ai/sketch/polish', {
    method: 'POST',
    body: {
      design_id: input.designId ?? null,
      input_data: {
        notes: input.notes ?? 'polish concept',
        image_base64: input.imageBase64,
        ...(input.fabricSwatchBase64
          ? { fabric_swatch_base64: input.fabricSwatchBase64 }
          : {}),
        magic_operation_id: input.magic_operation_id,
        studio_side: input.studio_side,
        reference_model_id: input.reference_model_id,
        idempotency_key: input.idempotency_key,
        shared_garment_spec: input.shared_garment_spec,
        source_revision: input.source_revision,
        content_fingerprint: contentFingerprint ?? undefined,
      },
    },
    signal: input.signal,
  })
}

/** GET /ai/personal-try-on/preflight — notice + budget (no billable work). */
export type PersonalTryOnPreflight = {
  enabled: boolean
  live_http: boolean
  consent_version: string
  notice_text: string
  notice_hash: string
  prompt_version: string
  estimate_cents: number
  max_exposure_cents: number
  fashn_enabled?: boolean
  fashn_configured?: boolean
  fashn_live_http?: boolean
  fashn_consent_version?: string | null
  fashn_notice_text?: string | null
  fashn_notice_hash?: string | null
  fashn_estimate_cents_per_call?: number | null
  fashn_prompt_version?: string | null
  fashn_realism_estimate_cents_per_piece?: number | null
  fashn_combined_estimate_cents_one_piece?: number | null
  fashn_one_click?: boolean
}

export async function fetchPersonalTryOnPreflight(
  signal?: AbortSignal,
): Promise<PersonalTryOnPreflight> {
  return apiRequest<PersonalTryOnPreflight>('/ai/personal-try-on/preflight', {
    method: 'GET',
    signal,
  })
}

export type FashnGarmentPrepareResult = {
  layout: 'one_piece' | 'two_piece' | string
  fashn_calls: number
  estimate_cents: number
  realism_calls?: number
  realism_estimate_cents?: number
  combined_estimate_cents?: number
  garment_fingerprint: string
  quality_ok?: boolean
  quality_notes?: string
  composite_preview_base64: string
  pieces: Array<{
    category: string
    image_base64: string
    bbox: number[]
    opaque_pixels: number
    fill_ratio?: number
    edge_ratio?: number
  }>
  notes: string
  consent_version: string
  notice_text: string
  notice_hash: string
  provider: string
  configured: boolean
  live_http: boolean
  openai_live_http?: boolean
}

export type FashnRealisticPiece = {
  category: string
  image_base64: string
  image_url?: string
  sha256?: string
}

/** POST /ai/personal-try-on/fashn/prepare — offline flat-lay preview (no paid call). */
export async function prepareFashnGarmentReference(
  garmentImageBase64: string,
  signal?: AbortSignal,
): Promise<FashnGarmentPrepareResult> {
  return apiRequest<FashnGarmentPrepareResult>('/ai/personal-try-on/fashn/prepare', {
    method: 'POST',
    body: { garment_image_base64: garmentImageBase64 },
    signal,
  })
}

export type EnqueueGarmentRealismInput = {
  croquisId: string
  croquisVersion: number
  garmentImageBase64: string
  platePieces: Array<{ category: string; image_base64: string }>
  garmentFingerprint: string
  idempotencyKey: string
  designId?: string | null
  consentAcknowledged: boolean
  consentVersion: string
  signal?: AbortSignal
}

/** POST /ai/personal-try-on/fashn/garment-realism — paid OpenAI product images. */
export async function enqueueFashnGarmentRealism(
  input: EnqueueGarmentRealismInput,
): Promise<AiJobRead> {
  return apiRequest<AiJobRead>('/ai/personal-try-on/fashn/garment-realism', {
    method: 'POST',
    body: {
      croquis_id: input.croquisId,
      croquis_version: input.croquisVersion,
      garment_image_base64: input.garmentImageBase64,
      plate_pieces: input.platePieces,
      garment_fingerprint: input.garmentFingerprint,
      idempotency_key: input.idempotencyKey,
      design_id: input.designId ?? null,
      consent_acknowledged: input.consentAcknowledged,
      consent_version: input.consentVersion,
    },
    signal: input.signal,
  })
}

export type PersonalTryOnInput = {
  croquisId: string
  croquisVersion: number
  garmentImageBase64: string
  idempotencyKey: string
  designId?: string | null
  sourceRevision: number
  contentFingerprint: string
  consentAcknowledged: boolean
  consentVersion: string
  /** Optional Studio-derived color/material/accessory hints (V2). */
  designHints?: string[] | null
  /** Explicit provider — never auto-switched after a refusal. */
  provider?: 'openai' | 'fashn'
  /** Owner-accepted realistic product plates (required for FASHN). */
  approvedGarmentPieces?: Array<{ category: string; image_base64: string }> | null
  garmentRealismJobId?: string | null
  signal?: AbortSignal
}

/** POST /ai/personal-try-on — photorealistic try-on on the owner's original photo. */
export async function enqueuePersonalTryOn(input: PersonalTryOnInput): Promise<AiJobRead> {
  const contentFingerprint = await toApiContentFingerprint(input.contentFingerprint)
  if (!contentFingerprint) {
    throw new ApiError('content_fingerprint is required for Try On Person', 400, null)
  }
  const designHints = (input.designHints ?? [])
    .filter((h): h is string => typeof h === 'string' && h.trim().length > 0)
    .map((h) => h.trim().slice(0, 120))
    .slice(0, 8)
  const provider = input.provider === 'fashn' ? 'fashn' : 'openai'
  return apiRequest<AiJobRead>('/ai/personal-try-on', {
    method: 'POST',
    body: {
      croquis_id: input.croquisId,
      croquis_version: input.croquisVersion,
      garment_image_base64: input.garmentImageBase64,
      idempotency_key: input.idempotencyKey,
      design_id: input.designId ?? null,
      source_revision: input.sourceRevision,
      content_fingerprint: contentFingerprint,
      consent_acknowledged: input.consentAcknowledged,
      consent_version: input.consentVersion,
      provider,
      ...(designHints.length ? { design_hints: designHints } : {}),
      ...(provider === 'fashn' && input.approvedGarmentPieces?.length
        ? {
            approved_garment_pieces: input.approvedGarmentPieces,
            garment_realism_job_id: input.garmentRealismJobId ?? null,
          }
        : {}),
    },
    signal: input.signal,
  })
}

export async function fetchAiJob(jobId: string, signal?: AbortSignal): Promise<AiJobRead> {
  return apiRequest<AiJobRead>(`/ai/jobs/${jobId}`, { signal })
}

export type MagicOperationJobsRead = {
  magic_operation_id: string
  jobs: AiJobRead[]
}

/**
 * Recover Front/Back jobs for a coordinated dual Magic operation without enqueueing.
 * Backend: GET /ai/magic-operations/{operationId}/jobs (PR #70).
 */
export async function fetchMagicOperationJobs(
  operationId: string,
  signal?: AbortSignal,
): Promise<MagicOperationJobsRead> {
  return apiRequest<MagicOperationJobsRead>(`/ai/magic-operations/${operationId}/jobs`, {
    signal,
  })
}

/**
 * Map operation job list → current Front/Back job ids using `input_data.studio_side`.
 *
 * PR #70 lists jobs oldest-first and retries a failed side with a new job id under the
 * same operation. Recovery must select the **latest** attempt per side (not the first /
 * oldest), so a failed-side retry is what we resume — never re-enqueue here.
 */
export function mapMagicOperationJobsBySide(jobs: AiJobRead[]): {
  frontJobId: string | null
  backJobId: string | null
} {
  let front: AiJobRead | null = null
  let back: AiJobRead | null = null
  for (const job of jobs) {
    const side = job.input_data?.studio_side
    if (side === 'front') front = preferCurrentMagicJob(front, job)
    if (side === 'back') back = preferCurrentMagicJob(back, job)
  }
  return { frontJobId: front?.id ?? null, backJobId: back?.id ?? null }
}

function preferCurrentMagicJob(prev: AiJobRead | null, next: AiJobRead): AiJobRead {
  if (!prev) return next
  const prevTs = Date.parse(prev.created_at)
  const nextTs = Date.parse(next.created_at)
  if (Number.isFinite(prevTs) && Number.isFinite(nextTs)) {
    if (nextTs > prevTs) return next
    if (nextTs < prevTs) return prev
  }
  // Timestamps equal/missing: prefer later list order (matches #70 oldest-first listing).
  return next
}

/** Authenticated look image (never relies on public /static/uploads). */
export async function fetchJobImageBlob(jobId: string, signal?: AbortSignal): Promise<Blob> {
  const headers: Record<string, string> = { Accept: 'image/*,application/octet-stream' }
  const tokens = tokenStore.get()
  if (tokens?.accessToken) {
    headers.Authorization = `Bearer ${tokens.accessToken}`
  }
  let response: Response
  try {
    response = await fetch(`${getApiBaseUrl()}/ai/jobs/${jobId}/image`, {
      method: 'GET',
      headers,
      signal,
    })
  } catch {
    throw new ApiError('Unable to reach FashionRise. Check that the API is running.', 0, null)
  }
  if (!response.ok) {
    let parsed: unknown = null
    try {
      parsed = await response.json()
    } catch {
      parsed = null
    }
    const message =
      typeof parsed === 'object' &&
      parsed !== null &&
      'detail' in parsed &&
      typeof (parsed as { detail: unknown }).detail === 'object' &&
      (parsed as { detail: { message?: unknown } }).detail !== null &&
      typeof (parsed as { detail: { message?: unknown } }).detail?.message === 'string'
        ? String((parsed as { detail: { message: string } }).detail.message)
        : `Image request failed (${response.status})`
    throw new ApiError(message, response.status, parsed)
  }
  const blob = await response.blob()
  if (!blob.size) throw new ApiError('Look image was empty', response.status, null)
  return blob
}
