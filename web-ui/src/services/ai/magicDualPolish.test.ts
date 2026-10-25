import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/services/api/client'
import * as magicApi from '@/services/ai/magicApi'
import {
  DualPolishUnavailableError,
  enqueueDualPolish,
} from '@/services/ai/magicDualPolish'

const dualInput = (): magicApi.PolishSketchDualInput => ({
  magic_operation_id: '11111111-1111-1111-1111-111111111111',
  shared_garment_spec: {
    notes: 'polish concept',
    colors: ['#1C1C1E'],
    main_colors: ['#1C1C1E'],
    details: 'model=female-straight;front_strokes=1;back_strokes=1',
    garment_category: 'studio',
  },
  source_revision: 2,
  content_fingerprint: 'fp-test',
  front: {
    image_base64: 'data:image/png;base64,aa',
    idempotency_key: '11111111-1111-1111-1111-111111111111:front',
  },
  back: {
    image_base64: 'data:image/png;base64,bb',
    idempotency_key: '11111111-1111-1111-1111-111111111111:back',
  },
})

describe('enqueueDualPolish', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('uses polish-dual when available', async () => {
    vi.spyOn(magicApi, 'enqueueSketchPolishDual').mockResolvedValue({
      magic_operation_id: '11111111-1111-1111-1111-111111111111',
      front_job: { id: 'jf', status: 'queued' } as magicApi.SketchPolishDualRead['front_job'],
      back_job: { id: 'jb', status: 'queued' } as magicApi.SketchPolishDualRead['back_job'],
    })
    const single = vi.spyOn(magicApi, 'enqueueSketchPolish')
    const result = await enqueueDualPolish(dualInput())
    expect(result.front_job_id).toBe('jf')
    expect(result.back_job_id).toBe('jb')
    expect(single).not.toHaveBeenCalled()
  })

  it('fails closed on 404 without sequential fallback', async () => {
    vi.spyOn(magicApi, 'enqueueSketchPolishDual').mockRejectedValue(
      new ApiError('Not found', 404, null),
    )
    const single = vi.spyOn(magicApi, 'enqueueSketchPolish')
    await expect(enqueueDualPolish(dualInput())).rejects.toBeInstanceOf(DualPolishUnavailableError)
    expect(single).not.toHaveBeenCalled()
  })

  it('posts BE field names source_revision and content_fingerprint', async () => {
    const spy = vi.spyOn(magicApi, 'enqueueSketchPolishDual').mockResolvedValue({
      magic_operation_id: '11111111-1111-1111-1111-111111111111',
      front_job: { id: 'jf', status: 'queued' } as magicApi.SketchPolishDualRead['front_job'],
      back_job: { id: 'jb', status: 'queued' } as magicApi.SketchPolishDualRead['back_job'],
    })
    await enqueueDualPolish(dualInput())
    const arg = spy.mock.calls[0]?.[0]
    expect(arg?.source_revision).toBe(2)
    expect(arg?.content_fingerprint).toBe('fp-test')
    expect(arg?.shared_garment_spec).toBeTruthy()
    expect(arg?.front.idempotency_key).toContain(':front')
    expect(arg?.back.idempotency_key).toContain(':back')
  })
})
