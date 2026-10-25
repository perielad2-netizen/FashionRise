import { ApiError, apiRequest, getApiBaseUrl } from '@/services/api/client'
import { tokenStore } from '@/services/auth/tokenStore'
import type { AiJobRead } from '@/services/ai/aiJobTypes'

export type PolishSidePayload = {
  image_base64: string
  notes?: string
  idempotency_key?: string
}

export type PolishSketchDualInput = {
  design_id?: string | null
  magic_operation_id?: string
  reference_model_id?: string
  notes?: string
  mood_notes?: string
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
  /** WEB-V4J dual-sided polish grouping (mock-friendly; server may ignore until wired). */
  magic_operation_id?: string
  studio_side?: 'front' | 'back'
  reference_model_id?: string
  signal?: AbortSignal
}

export async function enqueueSketchPolishDual(
  input: PolishSketchDualInput,
): Promise<SketchPolishDualRead> {
  return apiRequest<SketchPolishDualRead>('/ai/sketch/polish-dual', {
    method: 'POST',
    body: {
      design_id: input.design_id ?? null,
      magic_operation_id: input.magic_operation_id ?? null,
      reference_model_id: input.reference_model_id ?? null,
      notes: input.notes ?? 'polish concept',
      mood_notes: input.mood_notes,
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
      },
    },
    signal: input.signal,
  })
}

export async function fetchAiJob(jobId: string, signal?: AbortSignal): Promise<AiJobRead> {
  return apiRequest<AiJobRead>(`/ai/jobs/${jobId}`, { signal })
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
