import { act, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  login: vi.fn(),
  register: vi.fn(),
  restoreSession: vi.fn(),
  logoutLocal: vi.fn(),
  fetchMe: vi.fn(),
}))

const tokenStore = vi.hoisted(() => ({
  get: vi.fn(() => null as null | { accessToken: string; refreshToken: string }),
  set: vi.fn(),
  clear: vi.fn(),
}))

const fabricCache = vi.hoisted(() => ({
  bindFabricCacheToUser: vi.fn(),
}))

vi.mock('@/services/auth/authApi', () => ({
  login: (...args: unknown[]) => api.login(...args),
  register: (...args: unknown[]) => api.register(...args),
  restoreSession: (...args: unknown[]) => api.restoreSession(...args),
  logoutLocal: () => api.logoutLocal(),
  getGoogleOAuthStatus: async () => ({ google_oauth_enabled: false }),
  fetchMe: (...args: unknown[]) => api.fetchMe(...args),
}))

vi.mock('@/services/auth/tokenStore', () => ({ tokenStore }))

vi.mock('@/lib/fabricAssetCache', () => ({
  bindFabricCacheToUser: (...args: unknown[]) => fabricCache.bindFabricCacheToUser(...args),
}))

import { AuthProvider, useAuth } from '@/services/auth/AuthProvider'

function Probe() {
  const { user, isAuthenticated, login, register, logout } = useAuth()
  return (
    <div>
      <div data-testid="user-id">{user?.id ?? 'none'}</div>
      <div data-testid="auth">{isAuthenticated ? 'yes' : 'no'}</div>
      <button type="button" onClick={() => void login({ email: 'b@ex.com', password: 'pw' })}>
        login-b
      </button>
      <button
        type="button"
        onClick={() =>
          void register({
            email: 'c@ex.com',
            username: 'c',
            password: 'pw',
            invitationCode: 'code',
          })
        }
      >
        register-c
      </button>
      <button type="button" onClick={() => logout()}>
        logout
      </button>
    </div>
  )
}

const userA = {
  id: 'user-a',
  email: 'a@ex.com',
  username: 'a',
  is_active: true,
  is_admin: false,
  created_at: '2026-10-20T00:00:00Z',
}
const userB = { ...userA, id: 'user-b', email: 'b@ex.com', username: 'b' }
const userC = { ...userA, id: 'user-c', email: 'c@ex.com', username: 'c' }

describe('AuthProvider account switching', () => {
  beforeEach(() => {
    api.login.mockReset()
    api.register.mockReset()
    api.restoreSession.mockReset()
    api.logoutLocal.mockReset()
    api.fetchMe.mockReset()
    fabricCache.bindFabricCacheToUser.mockReset()
    tokenStore.get.mockReset()
    tokenStore.get.mockReturnValue(null)
    api.restoreSession.mockResolvedValue(null)
  })

  it('clears the previous user before login completes (no cross-account identity flash)', async () => {
    let resolveLogin: (v: { user: typeof userB; tokens: unknown }) => void = () => {}
    api.login.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveLogin = resolve
        }),
    )

    // Seed as user A via restore
    tokenStore.get.mockReturnValue({ accessToken: 'x', refreshToken: 'y' })
    api.restoreSession.mockResolvedValue(userA)

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )

    await waitFor(() => expect(screen.getByTestId('user-id')).toHaveTextContent('user-a'))

    await act(async () => {
      screen.getByRole('button', { name: 'login-b' }).click()
    })

    // Identity cleared immediately while the new session loads.
    await waitFor(() => expect(screen.getByTestId('user-id')).toHaveTextContent('none'))
    expect(screen.getByTestId('auth')).toHaveTextContent('no')

    await act(async () => {
      resolveLogin({ user: userB, tokens: {} })
    })

    await waitFor(() => expect(screen.getByTestId('user-id')).toHaveTextContent('user-b'))
    expect(fabricCache.bindFabricCacheToUser).toHaveBeenCalledWith(null)
    expect(fabricCache.bindFabricCacheToUser).toHaveBeenCalledWith('user-b')
  })

  it('clears the previous user before register completes', async () => {
    tokenStore.get.mockReturnValue({ accessToken: 'x', refreshToken: 'y' })
    api.restoreSession.mockResolvedValue(userA)

    let resolveRegister: (v: { user: typeof userC; tokens: unknown }) => void = () => {}
    api.register.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveRegister = resolve
        }),
    )

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )
    await waitFor(() => expect(screen.getByTestId('user-id')).toHaveTextContent('user-a'))

    await act(async () => {
      screen.getByRole('button', { name: 'register-c' }).click()
    })
    await waitFor(() => expect(screen.getByTestId('user-id')).toHaveTextContent('none'))

    await act(async () => {
      resolveRegister({ user: userC, tokens: {} })
    })
    await waitFor(() => expect(screen.getByTestId('user-id')).toHaveTextContent('user-c'))
  })

  it('logout clears identity', async () => {
    tokenStore.get.mockReturnValue({ accessToken: 'x', refreshToken: 'y' })
    api.restoreSession.mockResolvedValue(userA)

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )
    await waitFor(() => expect(screen.getByTestId('user-id')).toHaveTextContent('user-a'))

    await act(async () => {
      screen.getByRole('button', { name: 'logout' }).click()
    })
    expect(api.logoutLocal).toHaveBeenCalled()
    expect(screen.getByTestId('user-id')).toHaveTextContent('none')
    expect(fabricCache.bindFabricCacheToUser).toHaveBeenCalledWith(null)
  })

  describe('refreshUser session identity (token value equality)', () => {
    function RefreshProbe() {
      const { user, refreshUser, logout, login } = useAuth()
      return (
        <div>
          <div data-testid="user-id">{user?.id ?? 'none'}</div>
          <div data-testid="stars">{user?.ai_stars ?? 'none'}</div>
          <button type="button" onClick={() => void refreshUser()}>
            refresh
          </button>
          <button type="button" onClick={() => logout()}>
            logout
          </button>
          <button
            type="button"
            onClick={() => void login({ email: 'b@ex.com', password: 'pw' })}
          >
            login-b
          </button>
        </div>
      )
    }

    /** Mimic real tokenStore.get(): new object instance every call, same values while session is alive. */
    function installValueTokenStore(tokens: { accessToken: string; refreshToken: string } | null) {
      let current = tokens
      tokenStore.get.mockImplementation(() =>
        current ? { accessToken: current.accessToken, refreshToken: current.refreshToken } : null,
      )
      return {
        set: (next: { accessToken: string; refreshToken: string } | null) => {
          current = next
        },
      }
    }

    it('accepts /me when tokenStore.get() returns fresh objects with the same token values', async () => {
      const session = installValueTokenStore({ accessToken: 'tok-a', refreshToken: 'ref-a' })
      void session
      api.restoreSession.mockResolvedValue({ ...userA, ai_stars: 1_000_089 })
      api.fetchMe.mockResolvedValue({ ...userA, ai_stars: 1_000_079 })

      render(
        <AuthProvider>
          <RefreshProbe />
        </AuthProvider>,
      )
      await waitFor(() => expect(screen.getByTestId('user-id')).toHaveTextContent('user-a'))
      expect(screen.getByTestId('stars')).toHaveTextContent('1000089')

      // Prove get() yields distinct object identities with identical values.
      const a = tokenStore.get()
      const b = tokenStore.get()
      expect(a).not.toBe(b)
      expect(a).toEqual(b)

      await act(async () => {
        screen.getByRole('button', { name: 'refresh' }).click()
      })

      await waitFor(() => expect(screen.getByTestId('stars')).toHaveTextContent('1000079'))
      expect(screen.getByTestId('user-id')).toHaveTextContent('user-a')
    })

    it('rejects stale /me after logout during the request', async () => {
      const session = installValueTokenStore({ accessToken: 'tok-a', refreshToken: 'ref-a' })
      api.restoreSession.mockResolvedValue({ ...userA, ai_stars: 1_000_089 })

      let resolveMe: (v: typeof userA & { ai_stars: number }) => void = () => {}
      api.fetchMe.mockImplementation(
        () =>
          new Promise((resolve) => {
            resolveMe = resolve
          }),
      )

      render(
        <AuthProvider>
          <RefreshProbe />
        </AuthProvider>,
      )
      await waitFor(() => expect(screen.getByTestId('user-id')).toHaveTextContent('user-a'))

      await act(async () => {
        screen.getByRole('button', { name: 'refresh' }).click()
      })

      session.set(null)
      await act(async () => {
        screen.getByRole('button', { name: 'logout' }).click()
      })
      expect(screen.getByTestId('user-id')).toHaveTextContent('none')

      await act(async () => {
        resolveMe({ ...userA, ai_stars: 1_000_079 })
      })

      expect(screen.getByTestId('user-id')).toHaveTextContent('none')
      expect(screen.getByTestId('stars')).toHaveTextContent('none')
    })

    it('rejects previous-account /me after account switch', async () => {
      const session = installValueTokenStore({ accessToken: 'tok-a', refreshToken: 'ref-a' })
      api.restoreSession.mockResolvedValue({ ...userA, ai_stars: 1_000_089 })

      let resolveMe: (v: typeof userA & { ai_stars: number }) => void = () => {}
      api.fetchMe.mockImplementation(
        () =>
          new Promise((resolve) => {
            resolveMe = resolve
          }),
      )
      api.login.mockResolvedValue({
        user: { ...userB, ai_stars: 50 },
        tokens: {},
      })

      render(
        <AuthProvider>
          <RefreshProbe />
        </AuthProvider>,
      )
      await waitFor(() => expect(screen.getByTestId('user-id')).toHaveTextContent('user-a'))
      expect(screen.getByTestId('stars')).toHaveTextContent('1000089')

      await act(async () => {
        screen.getByRole('button', { name: 'refresh' }).click()
      })

      // Account switch replaces session tokens before the old /me resolves.
      session.set({ accessToken: 'tok-b', refreshToken: 'ref-b' })
      await act(async () => {
        screen.getByRole('button', { name: 'login-b' }).click()
      })
      await waitFor(() => expect(screen.getByTestId('user-id')).toHaveTextContent('user-b'))
      expect(screen.getByTestId('stars')).toHaveTextContent('50')

      await act(async () => {
        resolveMe({ ...userA, ai_stars: 1_000_079 })
      })

      // Previous account wallet must never paint onto the new session.
      expect(screen.getByTestId('user-id')).toHaveTextContent('user-b')
      expect(screen.getByTestId('stars')).toHaveTextContent('50')
      expect(screen.getByTestId('stars')).not.toHaveTextContent('1000079')
      expect(screen.getByTestId('stars')).not.toHaveTextContent('1000089')
    })
  })
})
