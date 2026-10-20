import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/auth/AuthProvider', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAuth: () => ({
    user: null,
    bootstrapping: false,
    isAuthenticated: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  }),
}))

vi.mock('@/pages/StudioPage', () => ({
  StudioPage: () => <div>Studio</div>,
}))

vi.mock('@/pages/RegisterPage', () => ({
  RegisterPage: () => <div>Register page body</div>,
}))

vi.mock('@/pages/LoginPage', () => ({
  LoginPage: () => <div>Sign in page</div>,
}))

describe('App /register UI gate', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.unstubAllEnvs()
  })

  it('redirects /register to login when registration UI is disabled', async () => {
    vi.stubEnv('VITE_REGISTRATION_UI_ENABLED', 'false')
    const App = (await import('@/App')).default
    render(
      <MemoryRouter initialEntries={['/register']}>
        <App />
      </MemoryRouter>,
    )
    expect(await screen.findByText('Sign in page')).toBeInTheDocument()
    expect(screen.queryByText('Register page body')).not.toBeInTheDocument()
  })

  it('renders RegisterPage when registration UI is enabled', async () => {
    vi.stubEnv('VITE_REGISTRATION_UI_ENABLED', 'true')
    const App = (await import('@/App')).default
    render(
      <MemoryRouter initialEntries={['/register']}>
        <App />
      </MemoryRouter>,
    )
    expect(await screen.findByText('Register page body')).toBeInTheDocument()
  })
})
