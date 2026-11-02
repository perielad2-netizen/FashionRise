import { describe, expect, it } from 'vitest'
import {
  SMART_TRY_ON_FAILURE,
  SMART_TRY_ON_STATUS,
  SMART_TRY_ON_STOP_WAITING,
  isOpenAiTryOnEligibleForMaxFallback,
  isOpenAiTryOnTerminalFailure,
} from './smartTryOn'

describe('smartTryOn (#178/#179)', () => {
  it('does not treat successful OpenAI delivery as terminal', () => {
    expect(
      isOpenAiTryOnTerminalFailure({
        status: 'completed',
        summary: 'ready',
        bullets: [],
        hasImage: true,
        jobId: 'j1',
      }),
    ).toBe(false)
    expect(
      isOpenAiTryOnTerminalFailure({
        status: 'completed_unverified',
        summary: 'structure flag',
        bullets: [],
        hasImage: true,
        jobId: 'j2',
      }),
    ).toBe(false)
  })

  it('treats hard OpenAI failures as terminal but moderation is not Max-eligible (#179)', () => {
    const failed = {
      status: 'failed' as const,
      summary: 'blocked',
      bullets: [],
      hasImage: false,
      jobId: 'j3',
    }
    const moderationJob = {
      id: 'j3',
      user_id: 'u',
      design_id: null,
      job_type: 'personal_try_on',
      status: 'failed' as const,
      input_data: {},
      result_data: { error_code: 'PROVIDER_MODERATION_BLOCKED' },
      error_message: 'blocked',
      created_at: '',
      updated_at: '',
    }
    expect(isOpenAiTryOnTerminalFailure(failed, moderationJob)).toBe(true)
    expect(isOpenAiTryOnEligibleForMaxFallback(failed, moderationJob)).toBe(false)

    const timeoutJob = {
      ...moderationJob,
      result_data: { error_code: 'PROVIDER_TIMEOUT' },
    }
    expect(isOpenAiTryOnEligibleForMaxFallback(failed, timeoutJob)).toBe(true)
  })

  it('keeps user-facing spinner/failure/stop copy provider-agnostic', () => {
    expect(SMART_TRY_ON_STATUS).toBe('Generating your try-on preview...')
    expect(SMART_TRY_ON_STATUS.toLowerCase()).not.toMatch(/fashn|openai|credit|¢/)
    expect(SMART_TRY_ON_FAILURE.toLowerCase()).not.toMatch(/fashn|openai|credit|¢/)
    expect(SMART_TRY_ON_STOP_WAITING.toLowerCase()).toMatch(/generation continues/)
    expect(SMART_TRY_ON_STOP_WAITING.toLowerCase()).toMatch(/does not cancel or refund/)
    expect(SMART_TRY_ON_STOP_WAITING.toLowerCase()).not.toMatch(/fashn|openai|¢/)
  })
})
