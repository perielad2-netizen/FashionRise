import { act, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  login: vi.fn(),
  register: vi.fn(),
  restoreSession: vi.fn(),
  logoutLocal: vi.fn(),
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
    fabricCache.bindFabricCacheToUser.mockReset()
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
})
