import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/services/api/client'
import { pollAiJobUntilSettled } from '@/services/ai/pollAiJob'
import type { AiJobRead } from '@/services/ai/aiJobTypes'

function job(partial: Partial<AiJobRead> & { id: string; status: string }): AiJobRead {
  return {
    user_id: 'u1',
    design_id: null,
    job_type: 'sketch_polish',
    input_data: {},
    result_data: partial.result_data ?? null,
    error_message: null,
    created_at: '2026-10-21T00:00:00Z',
    updated_at: '2026-10-21T00:00:00Z',
    ...partial,
  }
}

describe('pollAiJobUntilSettled', () => {
  it('returns when job completes', async () => {
    const fetchJob = vi
      .fn()
      .mockResolvedValueOnce(job({ id: 'j1', status: 'queued' }))
      .mockResolvedValueOnce(
        job({
          id: 'j1',
          status: 'completed',
          result_data: { summary: 'done', image_url: 'http://x/static/uploads/ai/a.png' },
        }),
      )
    const sleep = vi.fn().mockResolvedValue(undefined)
    const settled = await pollAiJobUntilSettled({
      jobId: 'j1',
      fetchJob,
      sleep,
      intervalMs: 1,
      maxAttempts: 10,
    })
    expect(settled.status).toBe('completed')
    expect(fetchJob).toHaveBeenCalledTimes(2)
  })

  it('retries transient network errors then completes', async () => {
    const fetchJob = vi
      .fn()
      .mockRejectedValueOnce(new ApiError('offline', 0, null))
      .mockResolvedValueOnce(job({ id: 'j2', status: 'completed', result_data: { summary: 'ok' } }))
    const sleep = vi.fn().mockResolvedValue(undefined)
    const settled = await pollAiJobUntilSettled({
      jobId: 'j2',
      fetchJob,
      sleep,
      intervalMs: 1,
      maxAttempts: 10,
    })
    expect(settled.id).toBe('j2')
  })

  it('recovers an existing completed job after poll timeout without re-enqueue', async () => {
    let calls = 0
    const fetchJob = vi.fn(async () => {
      calls += 1
      // Exhaust maxAttempts while queued, then recovery GETs see completed.
      if (calls <= 2) return job({ id: 'j3', status: 'queued' })
      return job({
        id: 'j3',
        status: 'completed',
        result_data: { summary: 'recovered', image_url: 'http://x/static/uploads/ai/b.png' },
      })
    })
    const sleep = vi.fn().mockResolvedValue(undefined)
    const settled = await pollAiJobUntilSettled({
      jobId: 'j3',
      fetchJob,
      sleep,
      intervalMs: 1,
      maxAttempts: 2,
    })
    expect(settled.status).toBe('completed')
    expect(settled.result_data?.summary).toBe('recovered')
    expect(fetchJob.mock.calls.every((c) => c[0] === 'j3')).toBe(true)
  })

  it('fail-fast on 401 without recovery loop spam', async () => {
    const fetchJob = vi.fn().mockRejectedValue(new ApiError('auth', 401, null))
    const sleep = vi.fn().mockResolvedValue(undefined)
    await expect(
      pollAiJobUntilSettled({ jobId: 'j4', fetchJob, sleep, intervalMs: 1, maxAttempts: 5 }),
    ).rejects.toMatchObject({ status: 401 })
    expect(fetchJob).toHaveBeenCalledTimes(1)
  })
})
