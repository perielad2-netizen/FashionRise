/**
 * #178/#179 — Smart invisible Try On helpers (OpenAI primary → Max Balanced 1k fallback).
 * Keep copy provider-agnostic for the normal user flow.
 */

import type { MagicLookResult } from '@/services/ai/aiJobTypes'
import type { AiJobRead } from '@/services/ai/aiJobTypes'

export const SMART_TRY_ON_STATUS = 'Generating your try-on preview...'

export const SMART_TRY_ON_FAILURE =
  'We could not create a try-on preview for this design. Your sketch is unchanged — you can edit and try again.'

export const SMART_TRY_ON_STOP_WAITING =
  'Stopped waiting. Generation continues on the server — use Recover result when you return. This does not cancel or refund the provider job.'

/** Technical failures that may authorize Max fallback (#179). */
const ELIGIBLE_FALLBACK_ERROR_CODES = new Set([
  'PROVIDER_TIMEOUT',
  'PROVIDER_FAILED',
  'GENERATION_FAILED',
  'PROVIDER_REJECTED',
])

/** Terminal but must NOT auto-Max (moderation / unknown → recover first). */
const EXCLUDED_FALLBACK_ERROR_CODES = new Set([
  'PROVIDER_MODERATION_BLOCKED',
  'PROVIDER_OUTCOME_UNKNOWN',
])

/** True when OpenAI try-on ended without a usable delivered image. */
export function isOpenAiTryOnTerminalFailure(
  look: Pick<MagicLookResult, 'status'> | null | undefined,
  _job?: AiJobRead | null,
): boolean {
  if (!look) return false
  // Successful delivery (including soft structure flag) must not trigger fallback.
  if (look.status === 'completed' || look.status === 'completed_unverified') {
    return false
  }
  return look.status === 'failed'
}

/**
 * #179 — Max fallback only for confirmed technical failures.
 * Moderation refusals and unknown outcomes stay on recover/reconcile.
 */
export function isOpenAiTryOnEligibleForMaxFallback(
  look: Pick<MagicLookResult, 'status'> | null | undefined,
  job?: AiJobRead | null,
): boolean {
  if (!isOpenAiTryOnTerminalFailure(look, job)) return false
  const code =
    typeof job?.result_data?.error_code === 'string'
      ? String(job.result_data.error_code).trim().toUpperCase()
      : ''
  if (job?.result_data?.reconciliation_required === true) return false
  if (code && EXCLUDED_FALLBACK_ERROR_CODES.has(code)) return false
  if (code && ELIGIBLE_FALLBACK_ERROR_CODES.has(code)) return true
  // Failed without a structured technical code — do not invent another paid generation.
  return false
}

export function newSmartOperationId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `smart-${Date.now()}`
}
