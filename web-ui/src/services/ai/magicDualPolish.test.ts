import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/services/api/client'
import * as magicApi from '@/services/ai/magicApi'
import {
  DualPolishUnavailableError,
  enqueueDualPolish,
} from '@/services/ai/magicDualPolish'

describe('enqueueDualPolish', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('uses polish-dual when available', async () => {
    vi.spyOn(magicApi, 'enqueueSketchPolishDual').mockResolvedValue({
      magic_operation_id: 'op-1',
      front_job: { id: 'jf', status: 'queued' } as magicApi.SketchPolishDualRead['front_job'],
      back_job: { id: 'jb', status: 'queued' } as magicApi.SketchPolishDualRead['back_job'],
    })
    const single = vi.spyOn(magicApi, 'enqueueSketchPolish')
    const result = await enqueueDualPolish({
      magic_operation_id: 'op-1',
      front: { image_base64: 'data:image/png;base64,aa' },
      back: { image_base64: 'data:image/png;base64,bb' },
    })
    expect(result.front_job_id).toBe('jf')
    expect(result.back_job_id).toBe('jb')
    expect(single).not.toHaveBeenCalled()
  })

  it('fails closed on 404 without sequential fallback', async () => {
    vi.spyOn(magicApi, 'enqueueSketchPolishDual').mockRejectedValue(
      new ApiError('Not found', 404, null),
    )
    const single = vi.spyOn(magicApi, 'enqueueSketchPolish')
    await expect(
      enqueueDualPolish({
        magic_operation_id: 'op-2',
        front: { image_base64: 'data:image/png;base64,aa' },
        back: { image_base64: 'data:image/png;base64,bb' },
      }),
    ).rejects.toBeInstanceOf(DualPolishUnavailableError)
    expect(single).not.toHaveBeenCalled()
  })
})
