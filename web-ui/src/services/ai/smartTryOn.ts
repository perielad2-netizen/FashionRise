/**
 * #178/#179/#180 — Smart invisible Try On helpers (OpenAI primary → Max Balanced 1k fallback).
 * Keep copy provider-agnostic for the normal user flow.
 */

import type { MagicLookResult } from '@/services/ai/aiJobTypes'
import type { AiJobRead } from '@/services/ai/aiJobTypes'

export const SMART_TRY_ON_STATUS = 'Generating your try-on preview...'

export const SMART_TRY_ON_FAILURE =
  'We could not create a try-on preview for this design. Your sketch is unchanged — you can edit and try again.'

export const SMART_TRY_ON_STOP_WAITING =
  'Stopped waiting. Any job already started on the server keeps running — use Recover result to resume. This does not refund or cancel provider charges.'

/** Technical failures that may authorize Max fallback. */
const ELIGIBLE_FALLBACK_ERROR_CODES = new Set([
  'PROVIDER_TIMEOUT',
  'PROVIDER_FAILED',
  'GENERATION_FAILED',
  'PROVIDER_REJECTED',
])

/** Terminal outcomes that must not auto-Max. */
const EXCLUDED_FALLBACK_ERROR_CODES = new Set(['PROVIDER_OUTCOME_UNKNOWN'])

function moderationStage(job?: AiJobRead | null): string {
  const pr = job?.result_data?.provider_rejection
  if (pr && typeof pr === 'object' && pr !== null && 'moderation_stage' in pr) {
    const stage = (pr as { moderation_stage?: unknown }).moderation_stage
    if (typeof stage === 'string') return stage.trim().toLowerCase()
  }
  const top = job?.result_data?.moderation_stage
  return typeof top === 'string' ? top.trim().toLowerCase() : ''
}

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
 * #180 — Max fallback for technical failures and output-stage moderation only.
 * Input moderation / unknown outcomes stay on recover/reconcile.
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
  if (code === 'PROVIDER_MODERATION_BLOCKED') {
    return moderationStage(job) === 'output'
  }
  if (code && ELIGIBLE_FALLBACK_ERROR_CODES.has(code)) return true
  return false
}

export function newSmartOperationId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `smart-${Date.now()}`
}

export function isSmartTryOnOperationId(operationId: string | null | undefined): boolean {
  return typeof operationId === 'string' && operationId.startsWith('smart:')
}

export function smartOperationIdFromRecord(operationId: string): string {
  return operationId.startsWith('smart:') ? operationId.slice('smart:'.length) : operationId
}
