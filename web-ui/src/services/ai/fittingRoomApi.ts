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
  stars_cost: number
  stars_cost_note: string
  max_outfit_pieces: number
  conflicting_category_sets: string[][]
  /** Owner-only Model B path — server true only when flag + allowlist match. */
  look_model_b_sunburst_available?: boolean
  look_model_b_sunburst_model?: string
}

export type FittingRoomGarmentPieceInput = {
  imageBase64: string
  category?: string
  /** fashionrise_look = Social Try on me plate (full look illustration). */
  source?: 'fashionrise_look' | 'upload'
}

export type FittingRoomTryOnInput = {
  personImageBase64: string
  garmentImageBase64?: string
  garmentPieces?: FittingRoomGarmentPieceInput[]
  idempotencyKey: string
  consentAcknowledged: boolean
  consentVersion: string
  garmentCategory?: string
  /** Social gallery item when try-on came from FashionRise feed (designer Stars). */
  sourceGalleryItemId?: string
  /** Owner-only: request Model B sunburst when preflight marks it available. */
  preferModelBSunburst?: boolean
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
      ...(input.garmentPieces?.length
        ? {
            garment_pieces: input.garmentPieces.map((p) => ({
              image_base64: p.imageBase64,
              category: p.category ?? 'auto',
              ...(p.source ? { source: p.source } : {}),
            })),
          }
        : { garment_image_base64: input.garmentImageBase64 }),
      idempotency_key: input.idempotencyKey,
      consent_acknowledged: input.consentAcknowledged,
      consent_version: input.consentVersion,
      garment_category: input.garmentCategory ?? 'auto',
      ...(input.sourceGalleryItemId
        ? { source_gallery_item_id: input.sourceGalleryItemId }
        : {}),
      ...(input.preferModelBSunburst ? { prefer_model_b_sunburst: true } : {}),
    },
    signal: input.signal,
  })
}
