/**
 * Port of Unity AiJobPollPolicy — keep aligned with
 * FashionRise/Assets/FashionRise/Infrastructure/Api/AiJobPollPolicy.cs and
 * backend/tests/test_magic_look_poll_policy.py.
 */

export const STATUS_REQUEST_TIMEOUT = 408
export const STATUS_TOO_MANY_REQUESTS = 429

export function isRetryableHttpStatus(statusCode: number): boolean {
  if (statusCode === STATUS_REQUEST_TIMEOUT) return true
  return statusCode >= 500 && statusCode <= 599
}

export function isFailFastHttpStatus(statusCode: number): boolean {
  if (statusCode === STATUS_TOO_MANY_REQUESTS) return true
  if (isRetryableHttpStatus(statusCode)) return false
  return statusCode >= 400 && statusCode <= 499
}

export function shouldRetryPollError(err: unknown, userCancelRequested: boolean): boolean {
  if (userCancelRequested) return false
  if (err && typeof err === 'object' && 'name' in err && (err as { name: string }).name === 'AbortError') {
    return false
  }
  if (err && typeof err === 'object' && 'status' in err) {
    const status = Number((err as { status: number }).status)
    if (status === 0) return true // network
    if (Number.isFinite(status)) return !isFailFastHttpStatus(status)
  }
  return true
}

export function shouldAttemptPolishRecovery(err: unknown, userCancelRequested: boolean): boolean {
  if (userCancelRequested) return false
  if (err && typeof err === 'object' && 'name' in err && (err as { name: string }).name === 'AbortError') {
    return false
  }
  if (err && typeof err === 'object' && 'status' in err) {
    const status = Number((err as { status: number }).status)
    if (Number.isFinite(status) && status > 0 && isFailFastHttpStatus(status)) return false
  }
  return true
}

/** Unity: 500 ms interval, 600 attempts (~5 min). */
export const MAGIC_POLL_INTERVAL_MS = 500
export const MAGIC_POLL_MAX_ATTEMPTS = 600
export const MAGIC_RECOVERY_ATTEMPTS = 5
export const MAGIC_RECOVERY_BASE_DELAY_MS = 750
