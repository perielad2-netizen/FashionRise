/**
 * #178/#179/#180 — Smart invisible Try On helpers (OpenAI primary → Max Balanced 1k fallback).
 * Keep copy provider-agnostic for the normal user flow.
 */

import type { MagicLookResult } from '@/services/ai/aiJobTypes'
import type { AiJobRead } from '@/services/ai/aiJobTypes'

export const SMART_TRY_ON_STATUS = 'Generating your try-on preview...'

export const SMART_TRY_ON_FAILURE =
  'We could not create a try-on preview for this design. Your sketch is unchanged — you can edit and try again.'

/** Input-stage safety block — Max must not run; be explicit so Recover is not a dead end. */
export const SMART_TRY_ON_INPUT_MODERATION =
  'The photo or sketch was blocked by image safety checks before a try-on could start. Try a different personal croquis photo, or simplify the sketch, then try again. Your sketch is unchanged.'

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
 * #180/#181 — Max fallback for technical failures and moderation blocks
 * (input or output, including sexual). Unknown outcomes stay terminal.
 * Max uses independent garment prep — it does not replay blocked OpenAI pixels.
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
  if (code === 'PROVIDER_MODERATION_BLOCKED') return true
  if (code && ELIGIBLE_FALLBACK_ERROR_CODES.has(code)) return true
  return false
}

/** Owner-facing copy when Smart Try-On stops without Max. */
export function smartTryOnTerminalFailureMessage(job?: AiJobRead | null): string {
  const code =
    typeof job?.result_data?.error_code === 'string'
      ? String(job.result_data.error_code).trim().toUpperCase()
      : ''
  const summary =
    typeof job?.result_data?.summary === 'string' ? job.result_data.summary.trim() : ''
  // Moderation is normally Max-eligible; this copy is only if Max could not start.
  if (code === 'PROVIDER_MODERATION_BLOCKED') {
    if (moderationStage(job) === 'input') return SMART_TRY_ON_INPUT_MODERATION
    // Prefer the server's human output-safety copy over the generic failure line.
    if (summary && summary.length < 320) return summary
    return SMART_TRY_ON_FAILURE
  }
  if (summary && summary.length < 280) return summary
  return SMART_TRY_ON_FAILURE
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
