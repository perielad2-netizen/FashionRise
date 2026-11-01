import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const authState = vi.hoisted(() => ({
  user: null as null | {
    id: string
    email: string
    username: string
    is_active: boolean
    is_admin: boolean
    created_at: string
  },
  bootstrapping: false,
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
}))

const studioMounts = vi.hoisted(() => [] as string[])

vi.mock('@/services/auth/AuthProvider', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAuth: () => ({
    user: authState.user,
    bootstrapping: authState.bootstrapping,
    login: authState.login,
    register: authState.register,
    logout: authState.logout,
    isAuthenticated: Boolean(authState.user),
  }),
}))

vi.mock('@/pages/StudioPage', () => ({
  StudioPage: () => {
    const id = authState.user?.id ?? 'none'
    studioMounts.push(id)
    return <div data-testid={`studio-for-${id}`}>Studio for {id}</div>
  },
}))

vi.mock('@/pages/LoginPage', () => ({
  LoginPage: () => <div>Login page</div>,
}))

vi.mock('@/pages/RegisterPage', () => ({
  RegisterPage: () => <div>Register page</div>,
}))

import App from '@/App'

function user(id: string) {
  return {
    id,
    email: `${id}@example.com`,
    username: id,
    is_active: true,
    is_admin: false,
    created_at: '2026-10-20T00:00:00Z',
  }
}

describe('UserScopedStudio account isolation', () => {
  beforeEach(() => {
    studioMounts.length = 0
    authState.user = null
    authState.bootstrapping = false
  })

  it('remounts Studio with a new key when the authenticated user changes', async () => {
    authState.user = user('user-a')

    const { rerender } = render(
      <MemoryRouter initialEntries={['/studio']}>
        <App />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('studio-for-user-a')).toBeInTheDocument()
    expect(studioMounts).toEqual(['user-a'])

    authState.user = user('user-b')
    rerender(
      <MemoryRouter initialEntries={['/studio']}>
        <App />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('studio-for-user-b')).toBeInTheDocument()
    expect(screen.queryByTestId('studio-for-user-a')).not.toBeInTheDocument()
    expect(studioMounts).toContain('user-b')
  })

  it('does not keep the previous Studio mount after logout', async () => {
    authState.user = user('user-a')

    const { rerender } = render(
      <MemoryRouter initialEntries={['/studio']}>
        <App />
      </MemoryRouter>,
    )
    expect(await screen.findByTestId('studio-for-user-a')).toBeInTheDocument()

    authState.user = null
    rerender(
      <MemoryRouter initialEntries={['/studio']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.queryByTestId('studio-for-user-a')).not.toBeInTheDocument()
    })
  })
})
