import { apiRequest } from '@/services/api/client'
import type { AiJobRead } from '@/services/ai/aiJobTypes'

export type FittingRoomPreflight = {
  enabled: boolean
  live_http: boolean
  consent_version: string
  notice_text: string
  prompt_version: string
  supported_categories: string[]
  preview_disclaimer: string
  ai_gate: boolean
}

export type FittingRoomTryOnInput = {
  personImageBase64: string
  garmentImageBase64: string
  idempotencyKey: string
  consentAcknowledged: boolean
  consentVersion: string
  garmentCategory?: string
  signal?: AbortSignal
}

export async function fetchFittingRoomPreflight(
  signal?: AbortSignal,
): Promise<FittingRoomPreflight> {
  return apiRequest<FittingRoomPreflight>('/ai/fitting-room/preflight', { signal })
}

export async function enqueueFittingRoomTryOn(
  input: FittingRoomTryOnInput,
): Promise<AiJobRead> {
  return apiRequest<AiJobRead>('/ai/fitting-room/try-on', {
    method: 'POST',
    body: {
      person_image_base64: input.personImageBase64,
      garment_image_base64: input.garmentImageBase64,
      idempotency_key: input.idempotencyKey,
      consent_acknowledged: input.consentAcknowledged,
      consent_version: input.consentVersion,
      garment_category: input.garmentCategory ?? 'auto',
    },
    signal: input.signal,
  })
}
