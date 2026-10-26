import { afterEach, describe, expect, it, vi } from 'vitest'
import type { AiJobRead } from '@/services/ai/aiJobTypes'
import {
  fetchMagicOperationJobs,
  mapMagicOperationJobsBySide,
} from '@/services/ai/magicApi'
import {
  clearMagicJobId,
  persistMagicOperation,
  readMagicJobId,
  readMagicOperation,
} from '@/services/ai/magicJobStore'
import { resolveDualMagicJobIds } from '@/services/ai/magicOperationRecovery'

const apiRequest = vi.fn()

vi.mock('@/services/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/api/client')>()
  return { ...actual, apiRequest: (...args: unknown[]) => apiRequest(...args) }
})

function job(id: string, side: 'front' | 'back', status: string = 'completed'): AiJobRead {
  return {
    id,
    user_id: 'u1',
    design_id: null,
    job_type: 'sketch_polish',
    status,
    input_data: { studio_side: side, magic_operation_id: 'op-1' },
    result_data: status === 'completed' ? { summary: `${side} ok`, image_url: `/img/${id}` } : null,
    error_message: status === 'failed' ? `${side} failed` : null,
    created_at: '2026-10-25T00:00:00.000Z',
    updated_at: '2026-10-25T00:00:00.000Z',
  }
}

describe('mapMagicOperationJobsBySide', () => {
  it('maps the latest Front/Back attempt (PR #70 oldest-first list + retry)', () => {
    const olderFront = job('jf', 'front')
    const newerFront = {
      ...job('jf2', 'front'),
      created_at: '2026-10-25T00:01:00.000Z',
    }
    const olderBack = job('jb', 'back')
    const retryBack = {
      ...job('jb-retry', 'back'),
      created_at: '2026-10-25T00:02:00.000Z',
      status: 'queued',
    }
    // Oldest-first order as returned by GET /ai/magic-operations/{id}/jobs
    expect(
      mapMagicOperationJobsBySide([olderFront, olderBack, newerFront, retryBack]),
    ).toEqual({ frontJobId: 'jf2', backJobId: 'jb-retry' })
  })
})

describe('fetchMagicOperationJobs', () => {
  afterEach(() => {
    apiRequest.mockReset()
  })

  it('GETs /ai/magic-operations/{id}/jobs without posting', async () => {
    apiRequest.mockResolvedValueOnce({
      magic_operation_id: 'op-1',
      jobs: [job('jf', 'front'), job('jb', 'back')],
    })
    const listed = await fetchMagicOperationJobs('op-1')
    expect(apiRequest).toHaveBeenCalledWith('/ai/magic-operations/op-1/jobs', {
      signal: undefined,
    })
    expect(listed.jobs).toHaveLength(2)
  })
})

describe('resolveDualMagicJobIds lost-response recovery', () => {
  afterEach(() => {
    apiRequest.mockReset()
    sessionStorage.clear()
    clearMagicJobId('user-1')
  })

  it('refreshes via GET even when both Front/Back ids are cached, preferring a newer Back retry', async () => {
    persistMagicOperation('user-1', {
      operationId: 'op-stale-cache',
      frontJobId: 'jf-old',
      backJobId: 'jb-old-failed',
      updatedAt: '2026-10-25T00:00:00.000Z',
    })
    const oldFront = {
      ...job('jf-old', 'front', 'completed'),
      created_at: '2026-10-25T00:00:00.000Z',
    }
    const oldBack = {
      ...job('jb-old-failed', 'back', 'failed'),
      created_at: '2026-10-25T00:00:01.000Z',
    }
    const retryBack = {
      ...job('jb-retry', 'back', 'queued'),
      created_at: '2026-10-25T00:00:30.000Z',
    }
    apiRequest.mockResolvedValueOnce({
      magic_operation_id: 'op-stale-cache',
      jobs: [oldFront, oldBack, retryBack],
    })

    const resolved = await resolveDualMagicJobIds('user-1')
    expect(apiRequest).toHaveBeenCalledTimes(1)
    expect(apiRequest.mock.calls[0]?.[0]).toBe('/ai/magic-operations/op-stale-cache/jobs')
    expect(apiRequest.mock.calls.some((c) => String(c[0]).includes('polish'))).toBe(false)
    expect(resolved).toEqual({
      operationId: 'op-stale-cache',
      frontJobId: 'jf-old',
      backJobId: 'jb-retry',
    })
    const stored = readMagicOperation('user-1')
    expect(stored?.frontJobId).toBe('jf-old')
    expect(stored?.backJobId).toBe('jb-retry')
    expect(readMagicJobId('user-1')).toBe('jf-old')
  })

  it('does not return stale cached ids when the operations GET fails', async () => {
    persistMagicOperation('user-1', {
      operationId: 'op-get-fail',
      frontJobId: 'jf-stale',
      backJobId: 'jb-stale',
      updatedAt: '2026-10-25T00:00:00.000Z',
    })
    apiRequest.mockRejectedValueOnce(new Error('network down'))
    await expect(resolveDualMagicJobIds('user-1')).rejects.toThrow('network down')
    const stored = readMagicOperation('user-1')
    expect(stored?.frontJobId).toBe('jf-stale')
    expect(stored?.backJobId).toBe('jb-stale')
    expect(apiRequest.mock.calls.some((c) => String(c[0]).includes('polish'))).toBe(false)
  })

  it('recovers Front/Back jobs from operationId when response was lost (refresh path)', async () => {
    persistMagicOperation('user-1', {
      operationId: 'op-lost',
      frontIdempotencyKey: 'op-lost:front',
      backIdempotencyKey: 'op-lost:back',
      updatedAt: '2026-10-25T00:00:00.000Z',
    })
    apiRequest.mockResolvedValueOnce({
      magic_operation_id: 'op-lost',
      jobs: [job('jf-rec', 'front'), job('jb-rec', 'back')],
    })

    const resolved = await resolveDualMagicJobIds('user-1')
    expect(apiRequest).toHaveBeenCalledTimes(1)
    expect(apiRequest.mock.calls[0]?.[0]).toBe('/ai/magic-operations/op-lost/jobs')
    expect(resolved).toEqual({
      operationId: 'op-lost',
      frontJobId: 'jf-rec',
      backJobId: 'jb-rec',
    })
    const stored = readMagicOperation('user-1')
    expect(stored?.frontJobId).toBe('jf-rec')
    expect(stored?.backJobId).toBe('jb-rec')
    expect(readMagicJobId('user-1')).toBe('jf-rec')
  })

  it('completes a partial local store (front only) from the operations list', async () => {
    persistMagicOperation('user-1', {
      operationId: 'op-partial',
      frontJobId: 'jf-known',
      updatedAt: '2026-10-25T00:00:00.000Z',
    })
    apiRequest.mockResolvedValueOnce({
      magic_operation_id: 'op-partial',
      jobs: [job('jf-known', 'front', 'completed'), job('jb-late', 'back', 'running')],
    })
    const resolved = await resolveDualMagicJobIds('user-1')
    expect(resolved?.frontJobId).toBe('jf-known')
    expect(resolved?.backJobId).toBe('jb-late')
  })

  it('returns null when jobs are delayed / not listed yet (no enqueue)', async () => {
    persistMagicOperation('user-1', {
      operationId: 'op-delay',
      updatedAt: '2026-10-25T00:00:00.000Z',
    })
    apiRequest.mockResolvedValueOnce({ magic_operation_id: 'op-delay', jobs: [] })
    await expect(resolveDualMagicJobIds('user-1')).resolves.toBeNull()
    expect(apiRequest.mock.calls.every((c) => String(c[0]).includes('/jobs'))).toBe(true)
    expect(apiRequest.mock.calls.some((c) => String(c[0]).includes('polish'))).toBe(false)
  })

  it('supports retry recovery when one side failed', async () => {
    persistMagicOperation('user-1', {
      operationId: 'op-fail',
      updatedAt: '2026-10-25T00:00:00.000Z',
    })
    apiRequest.mockResolvedValueOnce({
      magic_operation_id: 'op-fail',
      jobs: [job('jf', 'front', 'completed'), job('jb', 'back', 'failed')],
    })
    const resolved = await resolveDualMagicJobIds('user-1')
    expect(resolved).toEqual({
      operationId: 'op-fail',
      frontJobId: 'jf',
      backJobId: 'jb',
    })
  })
})
