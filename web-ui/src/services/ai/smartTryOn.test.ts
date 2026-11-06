import { describe, expect, it } from 'vitest'
import {
  SMART_TRY_ON_FAILURE,
  SMART_TRY_ON_INPUT_MODERATION,
  SMART_TRY_ON_STATUS,
  SMART_TRY_ON_STOP_WAITING,
  isOpenAiTryOnEligibleForMaxFallback,
  isOpenAiTryOnTerminalFailure,
  isSmartTryOnOperationId,
  smartTryOnTerminalFailureMessage,
} from './smartTryOn'
import { resolveSmartTryOnRecoverJobId } from './magicJobStore'

describe('smartTryOn (#178/#179/#180)', () => {
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
  })

  it('allows Max for input and output sexual moderation (#181)', () => {
    const failed = {
      status: 'failed' as const,
      summary: 'blocked',
      bullets: [],
      hasImage: false,
      jobId: 'j3',
    }
    const outputMod = {
      id: 'j3',
      user_id: 'u',
      design_id: null,
      job_type: 'personal_try_on',
      status: 'failed' as const,
      input_data: {},
      result_data: {
        error_code: 'PROVIDER_MODERATION_BLOCKED',
        summary:
          'Our image provider blocked the generated preview after creating it (output safety filter).',
        provider_rejection: { moderation_stage: 'output', categories: ['sexual'] },
      },
      error_message: 'blocked',
      created_at: '',
      updated_at: '',
    }
    const inputMod = {
      ...outputMod,
      result_data: {
        error_code: 'PROVIDER_MODERATION_BLOCKED',
        provider_rejection: { moderation_stage: 'input', categories: ['sexual'] },
      },
    }
    expect(isOpenAiTryOnTerminalFailure(failed, outputMod)).toBe(true)
    expect(isOpenAiTryOnEligibleForMaxFallback(failed, outputMod)).toBe(true)
    expect(isOpenAiTryOnEligibleForMaxFallback(failed, inputMod)).toBe(true)
    // Terminal copy only if Max path could not start.
    expect(smartTryOnTerminalFailureMessage(inputMod)).toBe(SMART_TRY_ON_INPUT_MODERATION)
    expect(smartTryOnTerminalFailureMessage(inputMod).toLowerCase()).toMatch(/safety checks/)
    expect(smartTryOnTerminalFailureMessage(outputMod).toLowerCase()).toMatch(/output safety/)

    const timeoutJob = {
      ...outputMod,
      result_data: { error_code: 'PROVIDER_TIMEOUT' },
    }
    expect(isOpenAiTryOnEligibleForMaxFallback(failed, timeoutJob)).toBe(true)

    const unknownJob = {
      ...outputMod,
      result_data: { error_code: 'PROVIDER_OUTCOME_UNKNOWN', reconciliation_required: true },
    }
    expect(isOpenAiTryOnEligibleForMaxFallback(failed, unknownJob)).toBe(false)
  })

  it('keeps spinner/failure/stop copy provider-agnostic and truthful', () => {
    expect(SMART_TRY_ON_STATUS).toBe('Generating your try-on preview...')
    expect(SMART_TRY_ON_STATUS.toLowerCase()).not.toMatch(/fashn|openai|credit|¢/)
    expect(SMART_TRY_ON_FAILURE.toLowerCase()).not.toMatch(/fashn|openai|credit|¢/)
    expect(SMART_TRY_ON_STOP_WAITING.toLowerCase()).toMatch(/recover/)
    expect(SMART_TRY_ON_STOP_WAITING.toLowerCase()).toMatch(/does not refund/)
  })

  it('distinguishes smart ops from dual Magic for recovery (#180)', () => {
    expect(isSmartTryOnOperationId('smart:abc')).toBe(true)
    expect(isSmartTryOnOperationId('dual-op-1')).toBe(false)
    expect(
      resolveSmartTryOnRecoverJobId({
        operationId: 'smart:abc',
        kind: 'smart_try_on',
        openaiJobId: 'o1',
        realismJobId: 'r1',
        maxJobId: 'm1',
        updatedAt: '',
      }),
    ).toBe('m1')
    expect(
      resolveSmartTryOnRecoverJobId({
        operationId: 'smart:abc',
        openaiJobId: 'o1',
        updatedAt: '',
      }),
    ).toBe('o1')
  })
})
