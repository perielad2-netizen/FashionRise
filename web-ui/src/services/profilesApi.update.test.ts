import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiRequest = vi.hoisted(() => vi.fn())

vi.mock('@/services/api/client', () => ({
  apiRequest: (...args: unknown[]) => apiRequest(...args),
  ApiError: class ApiError extends Error {
    status: number
    body: unknown
    constructor(message: string, status: number, body: unknown) {
      super(message)
      this.status = status
      this.body = body
    }
  },
  getApiBaseUrl: () => 'https://fashionrise.app/api/v1',
}))

import { updateMyProfile } from '@/services/profilesApi'

describe('updateMyProfile', () => {
  beforeEach(() => {
    apiRequest.mockReset()
    apiRequest.mockResolvedValue({
      id: 'p1',
      user_id: 'u1',
      display_name: 'PeriShilat',
      bio: '',
      avatar_url: '/api/v1/profiles/u1/avatar',
      style_tags: [],
    })
  })

  it('sends a plain object body (never double-JSON-stringified)', async () => {
    await updateMyProfile({ display_name: 'PeriShilat', bio: '' })
    expect(apiRequest).toHaveBeenCalledWith('/profiles/me', {
      method: 'PUT',
      body: { display_name: 'PeriShilat', bio: '' },
      signal: undefined,
    })
    const body = apiRequest.mock.calls[0]![1].body
    expect(typeof body).toBe('object')
    expect(typeof body).not.toBe('string')
  })
})
