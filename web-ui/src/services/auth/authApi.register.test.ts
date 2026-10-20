import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiRequest = vi.fn()
const tokenStore = {
  get: vi.fn(),
  set: vi.fn(),
  clear: vi.fn(),
}

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
}))

vi.mock('@/services/auth/tokenStore', () => ({ tokenStore }))

describe('authApi.register', () => {
  beforeEach(() => {
    apiRequest.mockReset()
    tokenStore.get.mockReset()
    tokenStore.set.mockReset()
    tokenStore.clear.mockReset()
  })

  it('clears prior tokens, posts invitation-backed register, then fetches me', async () => {
    apiRequest
      .mockResolvedValueOnce({
        access_token: 'a',
        refresh_token: 'r',
        token_type: 'bearer',
      })
      .mockResolvedValueOnce({
        id: 'u-new',
        email: 'new@example.com',
        username: 'newuser',
        is_active: true,
        is_admin: false,
        created_at: '2026-10-20T00:00:00Z',
      })

    const { register } = await import('@/services/auth/authApi')
    const result = await register({
      email: ' New@Example.com ',
      username: ' newuser ',
      password: 'StrongPass123!',
      displayName: 'New',
      invitationCode: '  invite-code-value-xxxxx  ',
    })

    expect(tokenStore.clear).toHaveBeenCalled()
    expect(apiRequest).toHaveBeenNthCalledWith(1, '/auth/register', {
      method: 'POST',
      body: {
        email: 'new@example.com',
        username: 'newuser',
        password: 'StrongPass123!',
        display_name: 'New',
        invitation_code: 'invite-code-value-xxxxx',
      },
      auth: false,
    })
    expect(tokenStore.set).toHaveBeenCalledWith({ accessToken: 'a', refreshToken: 'r' })
    expect(result.user.id).toBe('u-new')
    expect(result.user.is_admin).toBe(false)
  })
})
