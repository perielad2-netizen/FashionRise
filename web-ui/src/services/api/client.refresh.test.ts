import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const tokenStore = vi.hoisted(() => ({
  get: vi.fn(() => null as null | { accessToken: string; refreshToken: string }),
  set: vi.fn(),
  clear: vi.fn(),
}))

vi.mock('@/services/auth/tokenStore', () => ({ tokenStore }))

import { apiRequest, SESSION_EXPIRED_EVENT } from './client'

describe('apiRequest refresh-on-401 (V2-0012 / V2-0013)', () => {
  const originalFetch = globalThis.fetch

  beforeEach(() => {
    tokenStore.get.mockReset()
    tokenStore.set.mockReset()
    tokenStore.clear.mockReset()
    vi.stubEnv('VITE_API_BASE_URL', 'https://example.test/api/v1')
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
    vi.unstubAllEnvs()
  })

  it('refreshes once and retries the original request', async () => {
    tokenStore.get
      .mockReturnValueOnce({ accessToken: 'old-access', refreshToken: 'refresh-1' }) // first attempt
      .mockReturnValueOnce({ accessToken: 'old-access', refreshToken: 'refresh-1' }) // refresh gate
      .mockReturnValueOnce({ accessToken: 'old-access', refreshToken: 'refresh-1' }) // refreshAccessToken read
      .mockReturnValue({ accessToken: 'new-access', refreshToken: 'refresh-2' }) // retry

    const fetchMock = vi
      .fn()
      // original call → 401 Invalid token
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: 'Invalid token' }), {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      // refresh
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            access_token: 'new-access',
            refresh_token: 'refresh-2',
            token_type: 'bearer',
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      )
      // retry
      .mockResolvedValueOnce(
        new Response(JSON.stringify([{ id: 'd1', title: 'Try12' }]), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    globalThis.fetch = fetchMock as unknown as typeof fetch

    const rows = await apiRequest<Array<{ id: string; title: string }>>('/designs/my')
    expect(rows).toEqual([{ id: 'd1', title: 'Try12' }])
    expect(tokenStore.set).toHaveBeenCalledWith({
      accessToken: 'new-access',
      refreshToken: 'refresh-2',
    })
    expect(fetchMock).toHaveBeenCalledTimes(3)
    const retryAuth = (fetchMock.mock.calls[2][1] as RequestInit).headers as Record<string, string>
    expect(retryAuth.Authorization).toBe('Bearer new-access')
  })

  it('clears session and emits event when refresh fails', async () => {
    tokenStore.get.mockReturnValue({ accessToken: 'old-access', refreshToken: 'refresh-1' })
    const expired = vi.fn()
    window.addEventListener(SESSION_EXPIRED_EVENT, expired)

    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: 'Invalid token' }), { status: 401 }),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'Invalid token' }), { status: 401 }))

    await expect(apiRequest('/designs/my')).rejects.toMatchObject({
      status: 401,
      message: 'Your session expired. Please sign in again.',
    })
    expect(tokenStore.clear).toHaveBeenCalled()
    expect(expired).toHaveBeenCalled()
    window.removeEventListener(SESSION_EXPIRED_EVENT, expired)
  })

  it('does not attempt refresh when auth is disabled', async () => {
    tokenStore.get.mockReturnValue({ accessToken: 'a', refreshToken: 'r' })
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Invalid email or password.' }), { status: 401 }),
    )
    globalThis.fetch = fetchMock as unknown as typeof fetch

    await expect(
      apiRequest('/auth/login', {
        auth: false,
        method: 'POST',
        body: { email: 'a@b.c', password: 'x' },
      }),
    ).rejects.toMatchObject({ status: 401 })
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
