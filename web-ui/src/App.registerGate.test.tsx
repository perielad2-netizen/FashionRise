import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const authState = vi.hoisted(() => ({
  user: null as null,
  bootstrapping: false,
  isAuthenticated: false,
  registrationStatus: {
    mode: 'closed' as const,
    configured_mode: 'closed' as const,
    registration_available: false,
    requires_invitation: false,
    requires_email_verification: false,
    email_delivery_configured: false,
  },
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
}))

vi.mock('@/services/auth/AuthProvider', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAuth: () => authState,
}))

vi.mock('@/pages/StudioPage', () => ({
  StudioPage: () => <div>Studio</div>,
}))

vi.mock('@/pages/RegisterPage', async () => {
  const actual = await vi.importActual<typeof import('@/pages/RegisterPage')>(
    '@/pages/RegisterPage',
  )
  return actual
})

vi.mock('@/pages/LoginPage', () => ({
  LoginPage: () => <div>Sign in page</div>,
}))

describe('App /register capability gate', () => {
  beforeEach(() => {
    vi.resetModules()
    authState.registrationStatus = {
      mode: 'closed',
      configured_mode: 'closed',
      registration_available: false,
      requires_invitation: false,
      requires_email_verification: false,
      email_delivery_configured: false,
    }
  })

  it('redirects /register to login when backend registration is closed', async () => {
    const App = (await import('@/App')).default
    render(
      <MemoryRouter initialEntries={['/register']}>
        <App />
      </MemoryRouter>,
    )
    expect(await screen.findByText('Sign in page')).toBeInTheDocument()
  })

  it('renders RegisterPage when backend registration is available', async () => {
    authState.registrationStatus = {
      mode: 'public',
      configured_mode: 'public',
      registration_available: true,
      requires_invitation: false,
      requires_email_verification: true,
      email_delivery_configured: true,
    }
    const App = (await import('@/App')).default
    render(
      <MemoryRouter initialEntries={['/register']}>
        <App />
      </MemoryRouter>,
    )
    expect(await screen.findByRole('heading', { name: /create account/i })).toBeInTheDocument()
  })
})
