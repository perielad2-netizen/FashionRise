import { afterEach, describe, expect, it, vi } from 'vitest'
import { enqueueSketchPolish } from '@/services/ai/magicApi'
import { patchMagicOperationJob, persistMagicOperation, readMagicOperation } from '@/services/ai/magicJobStore'

const apiRequest = vi.fn()

vi.mock('@/services/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/api/client')>()
  return { ...actual, apiRequest: (...args: unknown[]) => apiRequest(...args) }
})

describe('magic dual enqueue structure', () => {
  afterEach(() => {
    apiRequest.mockReset()
    sessionStorage.clear()
  })

  it('posts operation metadata fields on polish enqueue', async () => {
    apiRequest.mockResolvedValueOnce({ id: 'job-front', status: 'queued' })
    await enqueueSketchPolish({
      imageBase64: 'data:image/png;base64,abc',
      designId: 'design-1',
      magic_operation_id: 'op-123',
      studio_side: 'front',
      reference_model_id: 'female-straight',
    })
    const body = apiRequest.mock.calls[0]?.[1]?.body as {
      design_id: string
      input_data: Record<string, unknown>
    }
    expect(body.design_id).toBe('design-1')
    expect(body.input_data.magic_operation_id).toBe('op-123')
    expect(body.input_data.studio_side).toBe('front')
    expect(body.input_data.reference_model_id).toBe('female-straight')
  })

  it('stores front and back job ids under one operation', () => {
    persistMagicOperation('user-1', { operationId: 'op-9', updatedAt: '2026-10-25T00:00:00.000Z' })
    patchMagicOperationJob('user-1', 'front', 'job-f')
    patchMagicOperationJob('user-1', 'back', 'job-b')
    const op = readMagicOperation('user-1')
    expect(op?.frontJobId).toBe('job-f')
    expect(op?.backJobId).toBe('job-b')
  })
})
