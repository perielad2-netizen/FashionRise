import { ApiError, apiRequest, getApiBaseUrl } from '@/services/api/client'
import { tokenStore } from '@/services/auth/tokenStore'
import type { AiJobRead } from '@/services/ai/aiJobTypes'
import type { SharedGarmentSpec } from '@/services/ai/magicGarmentSpec'

export type PolishSidePayload = {
  image_base64: string
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
      content_fingerprint: input.content_fingerprint ?? null,
      front: {
        image_base64: input.front.image_base64,
        notes: input.front.notes,
        idempotency_key: input.front.idempotency_key,
      },
      back: {
        image_base64: input.back.image_base64,
        notes: input.back.notes,
        idempotency_key: input.back.idempotency_key,
      },
    },
    signal: input.signal,
  })
}

export async function enqueueSketchPolish(input: PolishSketchInput): Promise<AiJobRead> {
  return apiRequest<AiJobRead>('/ai/sketch/polish', {
    method: 'POST',
    body: {
      design_id: input.designId ?? null,
      input_data: {
        notes: input.notes ?? 'polish concept',
        image_base64: input.imageBase64,
        magic_operation_id: input.magic_operation_id,
        studio_side: input.studio_side,
        reference_model_id: input.reference_model_id,
        idempotency_key: input.idempotency_key,
        shared_garment_spec: input.shared_garment_spec,
        source_revision: input.source_revision,
        content_fingerprint: input.content_fingerprint,
      },
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
