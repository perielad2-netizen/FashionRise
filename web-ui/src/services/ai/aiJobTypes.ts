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
}

export function extractImageUrl(resultData: Record<string, unknown> | null | undefined): string | null {
  if (!resultData) return null
  for (const key of ['image_url', 'imageUrl'] as const) {
    const value = resultData[key]
    if (typeof value === 'string' && value.trim()) return value.trim()
  }
  return null
}

export function extractMagicSummary(job: AiJobRead): string {
  if (job.status === 'failed') {
    return job.error_message?.trim() || 'Magic could not finish this look.'
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
  if (!structured || typeof structured !== 'object') return []
  const bullets = (structured as { polish_bullets?: unknown }).polish_bullets
  if (!Array.isArray(bullets)) return []
  return bullets.filter((b): b is string => typeof b === 'string' && b.trim().length > 0)
}

export function toMagicLookResult(job: AiJobRead): MagicLookResult {
  return {
    jobId: job.id,
    status: job.status,
    summary: extractMagicSummary(job),
    bullets: extractPolishBullets(job),
    hasImage: Boolean(extractImageUrl(job.result_data)),
  }
}
