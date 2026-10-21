import { describe, expect, it } from 'vitest'
import {
  isFailFastHttpStatus,
  isRetryableHttpStatus,
  shouldAttemptPolishRecovery,
  shouldRetryPollError,
} from '@/services/ai/aiJobPollPolicy'
import { ApiError } from '@/services/api/client'

describe('aiJobPollPolicy (Unity parity)', () => {
  it('classifies retryable vs fail-fast HTTP statuses', () => {
    expect(isRetryableHttpStatus(408)).toBe(true)
    expect(isRetryableHttpStatus(503)).toBe(true)
    expect(isFailFastHttpStatus(429)).toBe(true)
    expect(isFailFastHttpStatus(401)).toBe(true)
    expect(isFailFastHttpStatus(404)).toBe(true)
    expect(isFailFastHttpStatus(503)).toBe(false)
  })

  it('retries network and 5xx, not user cancel or 4xx fail-fast', () => {
    expect(shouldRetryPollError(new ApiError('net', 0, null), false)).toBe(true)
    expect(shouldRetryPollError(new ApiError('server', 503, null), false)).toBe(true)
    expect(shouldRetryPollError(new ApiError('auth', 401, null), false)).toBe(false)
    expect(shouldRetryPollError(new ApiError('x', 503, null), true)).toBe(false)
  })

  it('gates polish recovery like Unity', () => {
    expect(shouldAttemptPolishRecovery(new ApiError('blip', 0, null), false)).toBe(true)
    expect(shouldAttemptPolishRecovery(new ApiError('gone', 404, null), false)).toBe(false)
    expect(shouldAttemptPolishRecovery(new ApiError('x', 0, null), true)).toBe(false)
  })
})
