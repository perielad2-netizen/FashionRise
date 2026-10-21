import { ApiError } from '@/services/api/client'
import { fetchAiJob } from '@/services/ai/magicApi'
import type { AiJobRead } from '@/services/ai/aiJobTypes'
import {
  MAGIC_POLL_INTERVAL_MS,
  MAGIC_POLL_MAX_ATTEMPTS,
  MAGIC_RECOVERY_ATTEMPTS,
  MAGIC_RECOVERY_BASE_DELAY_MS,
  STATUS_TOO_MANY_REQUESTS,
  isFailFastHttpStatus,
  shouldAttemptPolishRecovery,
  shouldRetryPollError,
} from '@/services/ai/aiJobPollPolicy'

export type PollAiJobOptions = {
  jobId: string
  signal?: AbortSignal
  intervalMs?: number
  maxAttempts?: number
  sleep?: (ms: number, signal?: AbortSignal) => Promise<void>
  fetchJob?: typeof fetchAiJob
}

function defaultSleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(Object.assign(new Error('Aborted'), { name: 'AbortError' }))
      return
    }
    const timer = window.setTimeout(() => {
      signal?.removeEventListener('abort', onAbort)
      resolve()
    }, ms)
    const onAbort = () => {
      window.clearTimeout(timer)
      reject(Object.assign(new Error('Aborted'), { name: 'AbortError' }))
    }
    signal?.addEventListener('abort', onAbort, { once: true })
  })
}

function isTerminal(status: string): boolean {
  const s = status.toLowerCase()
  return s === 'completed' || s === 'failed'
}

/**
 * Unity WaitForJobCompletionAsync + polish recovery semantics for the browser.
 * Does not enqueue a new paid job — only GET /ai/jobs/{id}.
 */
export async function pollAiJobUntilSettled(options: PollAiJobOptions): Promise<AiJobRead> {
  const intervalMs = options.intervalMs ?? MAGIC_POLL_INTERVAL_MS
  const maxAttempts = options.maxAttempts ?? MAGIC_POLL_MAX_ATTEMPTS
  const sleep = options.sleep ?? defaultSleep
  const fetchJob = options.fetchJob ?? fetchAiJob
  const signal = options.signal

  try {
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      if (signal?.aborted) {
        throw Object.assign(new Error('Aborted'), { name: 'AbortError' })
      }
      try {
        const job = await fetchJob(options.jobId, signal)
        if (isTerminal(job.status)) return job
      } catch (err) {
        if (err instanceof ApiError && err.status === STATUS_TOO_MANY_REQUESTS) {
          throw new ApiError(
            'Rate limited while polling the AI job. Wait briefly and retry.',
            err.status,
            err.body,
          )
        }
        if (err instanceof ApiError && err.status > 0 && isFailFastHttpStatus(err.status)) {
          throw err
        }
        if (!shouldRetryPollError(err, Boolean(signal?.aborted))) {
          throw err
        }
      }
      await sleep(intervalMs, signal)
    }
    throw new ApiError(
      'AI job timed out while waiting for completion. Check that the API worker is running.',
      0,
      null,
    )
  } catch (err) {
    if (!shouldAttemptPolishRecovery(err, Boolean(signal?.aborted))) {
      throw err
    }
    return recoverExistingJob({
      jobId: options.jobId,
      signal,
      sleep,
      fetchJob,
      originalError: err,
    })
  }
}

async function recoverExistingJob(args: {
  jobId: string
  signal?: AbortSignal
  sleep: (ms: number, signal?: AbortSignal) => Promise<void>
  fetchJob: typeof fetchAiJob
  originalError: unknown
}): Promise<AiJobRead> {
  let lastError = args.originalError
  for (let recoveryAttempt = 0; recoveryAttempt < MAGIC_RECOVERY_ATTEMPTS; recoveryAttempt++) {
    if (args.signal?.aborted) {
      throw Object.assign(new Error('Aborted'), { name: 'AbortError' })
    }
    try {
      if (recoveryAttempt > 0) {
        await args.sleep(MAGIC_RECOVERY_BASE_DELAY_MS * recoveryAttempt, args.signal)
      }
      const recovered = await args.fetchJob(args.jobId, args.signal)
      if (isTerminal(recovered.status)) return recovered
    } catch (recoveryErr) {
      lastError = recoveryErr
      if (!shouldAttemptPolishRecovery(recoveryErr, Boolean(args.signal?.aborted))) {
        throw recoveryErr
      }
    }
  }
  throw lastError instanceof Error
    ? lastError
    : new ApiError('Unable to recover Magic job status', 0, null)
}

/** Resume polling for a previously started job id (no new enqueue). */
export async function recoverMagicJob(jobId: string, signal?: AbortSignal): Promise<AiJobRead> {
  return pollAiJobUntilSettled({ jobId, signal })
}
