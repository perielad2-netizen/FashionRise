import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiRequest = vi.fn()

vi.mock('@/services/api/client', () => ({
  apiRequest: (...args: unknown[]) => apiRequest(...args),
  ApiError: class ApiError extends Error {
    status: number
    constructor(message: string, status = 500) {
      super(message)
      this.status = status
    }
  },
  getApiBaseUrl: () => 'http://localhost',
}))

describe('listUserGallery', () => {
  beforeEach(() => {
    apiRequest.mockReset()
  })

  it('filters to public moderated looks only', async () => {
    apiRequest.mockResolvedValue([
      {
        id: 'ok',
        visibility: 'public',
        moderation_status: 'ok',
        user_id: 'u1',
        title: 'A',
        design_id: null,
        look_id: 'l1',
        image_url: null,
        rating_average: null,
        rating_count: 0,
        likes_count: 0,
        created_at: '',
        updated_at: '',
      },
      {
        id: 'private',
        visibility: 'private',
        moderation_status: 'ok',
        user_id: 'u1',
        title: 'B',
        design_id: null,
        look_id: 'l2',
        image_url: null,
        rating_average: null,
        rating_count: 0,
        likes_count: 0,
        created_at: '',
        updated_at: '',
      },
      {
        id: 'pending',
        visibility: 'public',
        moderation_status: 'pending',
        user_id: 'u1',
        title: 'C',
        design_id: null,
        look_id: 'l3',
        image_url: null,
        rating_average: null,
        rating_count: 0,
        likes_count: 0,
        created_at: '',
        updated_at: '',
      },
    ])

    const { listUserGallery } = await import('./galleryApi')
    const rows = await listUserGallery('u1')
    expect(apiRequest).toHaveBeenCalledWith('/gallery/user/u1', {
      method: 'GET',
      signal: undefined,
    })
    expect(rows.map((r) => r.id)).toEqual(['ok'])
  })
})
