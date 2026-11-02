import { describe, expect, it } from 'vitest'
import { extractMagicSummary, isMagicSafetyRefusal, type AiJobRead } from '@/services/ai/aiJobTypes'

function job(partial: Partial<AiJobRead>): AiJobRead {
  return {
    id: 'j1',
    user_id: 'u1',
    design_id: null,
    job_type: 'personal_try_on',
    status: 'failed',
    input_data: {},
    result_data: null,
    error_message: null,
    created_at: '2026-11-02T00:00:00Z',
    updated_at: '2026-11-02T00:00:00Z',
    ...partial,
  }
}

describe('Try On Person failure summary sanitization', () => {
  it('prefers structured PROVIDER_MODERATION_BLOCKED summary', () => {
    const summary = extractMagicSummary(
      job({
        error_message: 'This design could not be rendered by our image provider. Your sketch is saved. You can continue editing or choose Fashion Magic.',
        result_data: {
          summary:
            'This design could not be rendered by our image provider. Your sketch is saved. You can continue editing or choose Fashion Magic.',
          error_code: 'PROVIDER_MODERATION_BLOCKED',
          provider_rejection: { request_id: 'req_secret', moderation_stage: 'input' },
        },
      }),
    )
    expect(summary).toMatch(/could not be rendered by our image provider/i)
    expect(summary).not.toMatch(/req_secret|moderation_blocked|BadRequestError|sexual/i)
    expect(isMagicSafetyRefusal(summary)).toBe(true)
  })

  it('scrubs leaked raw OpenAI exception text from legacy error_message', () => {
    const summary = extractMagicSummary(
      job({
        error_message:
          "images.edit rejected by provider: BadRequestError status=400 code=moderation_blocked request_id=req_019dd categories=sexual Error code: 400 - {'error': {'message': 'Your request was rejected'}}",
      }),
    )
    expect(summary).toMatch(/could not be rendered by our image provider/i)
    expect(summary).not.toMatch(/BadRequestError|request_id|categories=sexual|Error code/i)
  })
})
