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
    vi.resetModules()
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

  it('clears tokens when register succeeds but /auth/me fails (no stale identity)', async () => {
    const { ApiError } = await import('@/services/api/client')
    apiRequest
      .mockResolvedValueOnce({
        access_token: 'a',
        refresh_token: 'r',
        token_type: 'bearer',
      })
      .mockRejectedValueOnce(new ApiError('me failed', 500, null))

    const { register } = await import('@/services/auth/authApi')
    await expect(
      register({
        email: 'new@example.com',
        username: 'newuser',
        password: 'StrongPass123!',
        invitationCode: 'invite-code-value-xxxxx',
      }),
    ).rejects.toThrow(/me failed/)

    expect(tokenStore.set).toHaveBeenCalledWith({ accessToken: 'a', refreshToken: 'r' })
    // Final clear drops the half-session so recovery is via sign-in, not a stale user.
    expect(tokenStore.clear.mock.calls.length).toBeGreaterThanOrEqual(2)
  })

  it('does not POST /auth/register a second time when only /auth/me failed', async () => {
    const { ApiError } = await import('@/services/api/client')
    apiRequest
      .mockResolvedValueOnce({
        access_token: 'a',
        refresh_token: 'r',
        token_type: 'bearer',
      })
      .mockRejectedValueOnce(new ApiError('me failed', 503, null))

    const { register } = await import('@/services/auth/authApi')
    await expect(
      register({
        email: 'new@example.com',
        username: 'newuser',
        password: 'StrongPass123!',
        invitationCode: 'invite-code-value-xxxxx',
      }),
    ).rejects.toBeTruthy()

    const registerPosts = apiRequest.mock.calls.filter((c) => c[0] === '/auth/register')
    expect(registerPosts).toHaveLength(1)
  })
})

describe('authApi.login account switch', () => {
  beforeEach(() => {
    apiRequest.mockReset()
    tokenStore.get.mockReset()
    tokenStore.set.mockReset()
    tokenStore.clear.mockReset()
    vi.resetModules()
  })

  it('clears prior tokens before applying the new login session', async () => {
    apiRequest
      .mockResolvedValueOnce({
        access_token: 'b',
        refresh_token: 's',
        token_type: 'bearer',
      })
      .mockResolvedValueOnce({
        id: 'u-b',
        email: 'b@example.com',
        username: 'userb',
        is_active: true,
        is_admin: false,
        created_at: '2026-10-20T00:00:00Z',
      })

    const { login } = await import('@/services/auth/authApi')
    const result = await login({ email: 'b@example.com', password: 'pw' })
    expect(tokenStore.clear).toHaveBeenCalled()
    expect(result.user.id).toBe('u-b')
  })

  it('clears tokens when login succeeds but /auth/me fails', async () => {
    const { ApiError } = await import('@/services/api/client')
    apiRequest
      .mockResolvedValueOnce({
        access_token: 'b',
        refresh_token: 's',
        token_type: 'bearer',
      })
      .mockRejectedValueOnce(new ApiError('me failed', 500, null))

    const { login } = await import('@/services/auth/authApi')
    await expect(login({ email: 'b@example.com', password: 'pw' })).rejects.toThrow(/me failed/)
    expect(tokenStore.clear.mock.calls.length).toBeGreaterThanOrEqual(2)
  })
})
