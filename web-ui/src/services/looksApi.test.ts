import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/services/api/client'
import {
  deleteLook,
  getLook,
  listLooks,
  lookThumbnailJobId,
  updateLook,
  type LookRecord,
} from './looksApi'

const apiRequest = vi.fn()

vi.mock('@/services/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/api/client')>()
  return {
    ...actual,
    apiRequest: (...args: unknown[]) => apiRequest(...args),
  }
})

const SAMPLE: LookRecord = {
  id: 'op-1',
  title: 'Look · Oct 26, 2026',
  is_favorite: false,
  is_archived: false,
  kind: 'dual',
  created_at: '2026-10-26T10:00:00Z',
  updated_at: '2026-10-26T10:00:00Z',
  front: {
    job_id: 'jf',
    studio_side: 'front',
    has_image: true,
    summary: 'front',
    created_at: '2026-10-26T10:00:00Z',
  },
  back: {
    job_id: 'jb',
    studio_side: 'back',
    has_image: true,
    summary: 'back',
    created_at: '2026-10-26T10:01:00Z',
  },
  design_id: null,
  magic_operation_id: 'op-1',
}

describe('looksApi', () => {
  beforeEach(() => {
    apiRequest.mockReset()
  })

  it('lists looks with filter/search/pagination query', async () => {
    apiRequest.mockResolvedValue({ items: [SAMPLE], total: 1, limit: 24, offset: 0 })
    const result = await listLooks({ filter: 'favorites', q: 'blush', limit: 12, offset: 24 })
    expect(apiRequest).toHaveBeenCalledWith(
      '/looks?filter=favorites&q=blush&limit=12&offset=24',
      expect.objectContaining({ method: 'GET' }),
    )
    expect(result.items[0].id).toBe('op-1')
  })

  it('gets and patches a look', async () => {
    apiRequest.mockResolvedValueOnce(SAMPLE)
    await getLook('op-1')
    expect(apiRequest).toHaveBeenCalledWith('/looks/op-1', expect.objectContaining({ method: 'GET' }))

    apiRequest.mockResolvedValueOnce({ ...SAMPLE, title: 'Runway', is_favorite: true })
    await updateLook('op-1', { title: 'Runway', is_favorite: true })
    expect(apiRequest).toHaveBeenCalledWith(
      '/looks/op-1',
      expect.objectContaining({
        method: 'PATCH',
        body: { title: 'Runway', is_favorite: true },
      }),
    )
  })

  it('picks front thumbnail job when available', () => {
    expect(lookThumbnailJobId(SAMPLE)).toBe('jf')
    expect(
      lookThumbnailJobId({
        ...SAMPLE,
        front: { ...SAMPLE.front!, has_image: false },
      }),
    ).toBe('jb')
  })

  it('deletes a look on 204', async () => {
    apiRequest.mockResolvedValueOnce(undefined)
    await expect(deleteLook('op-1')).resolves.toEqual({ ok: true, alreadyGone: false })
    expect(apiRequest).toHaveBeenCalledWith('/looks/op-1', expect.objectContaining({ method: 'DELETE' }))
  })

  it('treats DELETE 404 as success only when look is absent', async () => {
    apiRequest
      .mockRejectedValueOnce(new ApiError('missing', 404, null))
      .mockResolvedValueOnce({ items: [], total: 0, limit: 100, offset: 0 }) // all
      .mockResolvedValueOnce({ items: [], total: 0, limit: 100, offset: 0 }) // archived
      .mockResolvedValueOnce({ items: [], total: 0, limit: 100, offset: 0 }) // favorites
    await expect(deleteLook('op-1')).resolves.toEqual({ ok: true, alreadyGone: true })
  })

  it('does not claim success when DELETE 404 but look still listed', async () => {
    apiRequest
      .mockRejectedValueOnce(new ApiError('missing', 404, null))
      .mockResolvedValueOnce({ items: [SAMPLE], total: 1, limit: 100, offset: 0 })
    const result = await deleteLook('op-1')
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.canRetry).toBe(true)
  })
})
