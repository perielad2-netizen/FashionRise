/**
 * #178 — Smart invisible Try On helpers (OpenAI primary → Max Balanced 1k fallback).
 * Keep copy provider-agnostic for the normal user flow.
 */

import type { MagicLookResult } from '@/services/ai/aiJobTypes'
import type { AiJobRead } from '@/services/ai/aiJobTypes'

export const SMART_TRY_ON_STATUS = 'Generating your try-on preview...'

export const SMART_TRY_ON_FAILURE =
  'We could not create a try-on preview for this design. Your sketch is unchanged — you can edit and try again.'

const TERMINAL_ERROR_CODES = new Set([
  'PROVIDER_MODERATION_BLOCKED',
  'PROVIDER_REJECTED',
  'PROVIDER_OUTCOME_UNKNOWN',
  'PROVIDER_TIMEOUT',
  'PROVIDER_FAILED',
  'GENERATION_FAILED',
])

/** True when OpenAI try-on ended without a usable delivered image. */
export function isOpenAiTryOnTerminalFailure(
  look: Pick<MagicLookResult, 'status'> | null | undefined,
  job?: AiJobRead | null,
): boolean {
  if (!look) return false
  // Successful delivery (including soft structure flag) must not trigger fallback.
  if (look.status === 'completed' || look.status === 'completed_unverified') {
    return false
  }
  if (look.status !== 'failed') return false
  const code =
    typeof job?.result_data?.error_code === 'string'
      ? String(job.result_data.error_code).trim().toUpperCase()
      : ''
  if (code && TERMINAL_ERROR_CODES.has(code)) return true
  // Failed without a structured code still counts as a terminal non-result.
  return true
}

export function newSmartOperationId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `smart-${Date.now()}`
}
