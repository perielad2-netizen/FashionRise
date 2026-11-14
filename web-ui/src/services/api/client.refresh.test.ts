import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const tokenStore = vi.hoisted(() => ({
  get: vi.fn(() => null as null | { accessToken: string; refreshToken: string }),
  set: vi.fn(),
  clear: vi.fn(),
}))

vi.mock('@/services/auth/tokenStore', () => ({ tokenStore }))

import { apiRequest, refreshAccessToken, SESSION_EXPIRED_EVENT } from './client'

type Tokens = { accessToken: string; refreshToken: string }

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

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
      .mockReturnValueOnce({ accessToken: 'old-access', refreshToken: 'refresh-1' }) // tokensAt401
      .mockReturnValueOnce({ accessToken: 'old-access', refreshToken: 'refresh-1' }) // refreshAccessToken read
      .mockReturnValueOnce({ accessToken: 'old-access', refreshToken: 'refresh-1' }) // post-fetch match
      .mockReturnValueOnce({ accessToken: 'old-access', refreshToken: 'refresh-1' }) // pre-set match
      .mockReturnValue({ accessToken: 'new-access', refreshToken: 'refresh-2' }) // retry

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: 'Invalid token' }), {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
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

  it('discards refresh response if logout clears tokens mid-flight', async () => {
    const accountA: Tokens = { accessToken: 'a-access', refreshToken: 'a-refresh' }
    tokenStore.get.mockReturnValue(accountA)

    const refreshGate = deferred<Response>()
    globalThis.fetch = vi.fn().mockReturnValue(refreshGate.promise) as unknown as typeof fetch

    const pending = refreshAccessToken()
    // Logout while refresh HTTP is outstanding.
    tokenStore.get.mockReturnValue(null)

    refreshGate.resolve(
      new Response(
        JSON.stringify({
          access_token: 'stale-access',
          refresh_token: 'stale-refresh',
          token_type: 'bearer',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    expect(await pending).toBe(false)
    expect(tokenStore.set).not.toHaveBeenCalled()
    expect(tokenStore.clear).not.toHaveBeenCalled()
  })

  it('discards refresh response and never clears a newer account after switch', async () => {
    const accountA: Tokens = { accessToken: 'a-access', refreshToken: 'a-refresh' }
    const accountB: Tokens = { accessToken: 'b-access', refreshToken: 'b-refresh' }
    tokenStore.get.mockReturnValue(accountA)

    const refreshGate = deferred<Response>()
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: 'Invalid token' }), { status: 401 }),
      )
      .mockReturnValueOnce(refreshGate.promise)
    globalThis.fetch = fetchMock as unknown as typeof fetch

    const pending = apiRequest('/designs/my')
    // Wait until refresh fetch is in flight, then switch accounts.
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    tokenStore.get.mockReturnValue(accountB)

    refreshGate.resolve(
      new Response(
        JSON.stringify({
          access_token: 'a-new-access',
          refresh_token: 'a-new-refresh',
          token_type: 'bearer',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    await expect(pending).rejects.toMatchObject({ status: 401 })
    expect(tokenStore.set).not.toHaveBeenCalled()
    expect(tokenStore.clear).not.toHaveBeenCalled()
    expect(tokenStore.get()).toEqual(accountB)
  })

  it('single-flights concurrent 401s: one refresh, both retries use new tokens', async () => {
    const old: Tokens = { accessToken: 'old-access', refreshToken: 'refresh-1' }
    const next: Tokens = { accessToken: 'new-access', refreshToken: 'refresh-2' }
    let live: Tokens | null = old
    tokenStore.get.mockImplementation(() => live)
    tokenStore.set.mockImplementation((tokens: Tokens) => {
      live = tokens
    })

    const refreshGate = deferred<Response>()
    let refreshCalls = 0
    let resourceCalls = 0

    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (String(url).includes('/auth/refresh')) {
        refreshCalls += 1
        return refreshGate.promise
      }
      resourceCalls += 1
      if (resourceCalls <= 2) {
        return Promise.resolve(
          new Response(JSON.stringify({ detail: 'Invalid token' }), { status: 401 }),
        )
      }
      return Promise.resolve(
        new Response(JSON.stringify({ ok: true, n: resourceCalls }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    })
    globalThis.fetch = fetchMock as unknown as typeof fetch

    const a = apiRequest<{ ok: boolean }>('/designs/my')
    const b = apiRequest<{ ok: boolean }>('/looks/mine')
    await vi.waitFor(() => expect(refreshCalls).toBe(1))

    refreshGate.resolve(
      new Response(
        JSON.stringify({
          access_token: 'new-access',
          refresh_token: 'refresh-2',
          token_type: 'bearer',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    await expect(a).resolves.toMatchObject({ ok: true })
    await expect(b).resolves.toMatchObject({ ok: true })
    expect(refreshCalls).toBe(1)
    expect(resourceCalls).toBe(4) // two 401s + two retries
    expect(tokenStore.set).toHaveBeenCalledTimes(1)
    expect(tokenStore.set).toHaveBeenCalledWith(next)
    expect(tokenStore.clear).not.toHaveBeenCalled()

    const resourceRetryAuths = fetchMock.mock.calls
      .filter(([url]) => !String(url).includes('/auth/refresh'))
      .slice(-2)
      .map((call) => (call[1] as RequestInit).headers as Record<string, string>)
      .map((h) => h.Authorization)
    expect(resourceRetryAuths).toEqual(['Bearer new-access', 'Bearer new-access'])
  })
})
