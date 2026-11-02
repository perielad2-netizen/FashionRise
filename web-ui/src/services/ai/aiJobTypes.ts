export type AiJobStatus = 'queued' | 'running' | 'completed' | 'failed' | string

export type AiJobRead = {
  id: string
  user_id: string
  design_id: string | null
  job_type: string
  status: AiJobStatus
  input_data: Record<string, unknown>
  result_data: Record<string, unknown> | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export type MagicLookResult = {
  jobId: string
  status: AiJobStatus
  summary: string
  bullets: string[]
  hasImage: boolean
  /** #171 — verified structure failure (not ordinary inconclusive/not_applicable). */
  fidelityOk?: boolean | null
  structureReviewState?: string | null
  structureReviewMessage?: string | null
  /** True when UI must warn and must not present as an accepted My Look. */
  structureRejected?: boolean
}

export function extractImageUrl(resultData: Record<string, unknown> | null | undefined): string | null {
  if (!resultData) return null
  for (const key of ['image_url', 'imageUrl'] as const) {
    const value = resultData[key]
    if (typeof value === 'string' && value.trim()) return value.trim()
  }
  return null
}

const RAW_PROVIDER_LEAK =
  /BadRequestError|moderation_blocked|request_id=|Error code:\s*400|categories=sexual|Your request was rejected/i

const TRY_ON_MODERATION_FALLBACK =
  'This design could not be rendered by our image provider. Your sketch is saved. You can continue editing or choose Fashion Magic.'

/** True when the provider refused the edit under safety/content-policy rules. */
export function isMagicSafetyRefusal(summary: string | null | undefined): boolean {
  if (!summary) return false
  return /safety rules|content policy|content_policy|could not edit this sketch under|PROVIDER_MODERATION_BLOCKED|could not be rendered by our image provider/i.test(
    summary,
  )
}

function sanitizedFailedSummary(job: AiJobRead): string {
  const data = job.result_data
  const code = typeof data?.error_code === 'string' ? data.error_code : ''
  const structured =
    typeof data?.summary === 'string' && data.summary.trim() ? data.summary.trim() : null

  // Prefer structured owner-safe summary from the worker.
  if (structured && !RAW_PROVIDER_LEAK.test(structured)) {
    if (code === 'PROVIDER_MODERATION_BLOCKED' || isMagicSafetyRefusal(structured)) {
      return structured
    }
    return structured
  }

  const raw = job.error_message?.trim() || structured || 'Magic could not finish this look.'
  if (code === 'PROVIDER_MODERATION_BLOCKED' || /moderation_blocked/i.test(raw)) {
    return TRY_ON_MODERATION_FALLBACK
  }
  if (RAW_PROVIDER_LEAK.test(raw)) {
    return job.job_type === 'personal_try_on'
      ? TRY_ON_MODERATION_FALLBACK
      : 'This look could not be rendered by our image provider. Your sketch is unchanged.'
  }
  if (isMagicSafetyRefusal(raw)) {
    return (
      `${raw} Edit the sketch, then start a new Magic operation — ` +
      `identical retries are not sent automatically.`
    )
  }
  return raw
}

export function extractMagicSummary(job: AiJobRead): string {
  if (job.status === 'failed') {
    return sanitizedFailedSummary(job)
  }
  const data = job.result_data
  if (!data) return job.status
  const summary = data.summary
  if (typeof summary === 'string' && summary.trim()) return summary.trim()
  const message = data.message
  if (typeof message === 'string' && message.trim()) return message.trim()
  return job.status
}

export function extractPolishBullets(job: AiJobRead): string[] {
  const structured = job.result_data?.structured
  if (structured && typeof structured === 'object') {
    const bullets = (structured as { polish_bullets?: unknown }).polish_bullets
    if (Array.isArray(bullets)) {
      return bullets.filter((b): b is string => typeof b === 'string' && b.trim().length > 0)
    }
  }
  // Try On Person (and similar) store bullets at result_data.bullets.
  const top = job.result_data?.bullets
  if (Array.isArray(top)) {
    return top.filter((b): b is string => typeof b === 'string' && b.trim().length > 0)
  }
  return []
}

export function toMagicLookResult(job: AiJobRead): MagicLookResult {
  // #170/#171 — only verified structure failures become completed_unverified in the UI.
  // not_applicable / inconclusive keep ordinary completed presentation.
  const data = job.result_data
  const dataStatus = typeof data?.status === 'string' ? String(data.status) : null
  const fidelityOkRaw = data?.fidelity_ok
  const fidelityOk =
    fidelityOkRaw === false ? false : fidelityOkRaw === true ? true : null
  const review =
    data?.structure_review && typeof data.structure_review === 'object'
      ? (data.structure_review as Record<string, unknown>)
      : null
  const structureReviewState =
    typeof review?.state === 'string' ? String(review.state) : null
  const structureReviewMessage =
    typeof review?.message === 'string' ? String(review.message) : null
  // Only verified failures downgrade presentation. Historical #170 "unverified" ordinary
  // outfits (completed_unverified without fidelity_ok=false) stay ordinary completed.
  const structureRejected = fidelityOk === false || structureReviewState === 'failed'
  const status: AiJobStatus =
    job.status === 'completed' && structureRejected
      ? 'completed_unverified'
      : job.status === 'completed' && dataStatus === 'completed_unverified' && !structureRejected
        ? 'completed'
        : job.status
  return {
    jobId: job.id,
    status,
    summary: extractMagicSummary(job),
    bullets: extractPolishBullets(job),
    hasImage: Boolean(extractImageUrl(job.result_data)),
    fidelityOk,
    structureReviewState,
    structureReviewMessage,
    structureRejected,
  }
}
