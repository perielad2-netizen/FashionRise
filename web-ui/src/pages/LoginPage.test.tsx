import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { LoginPage } from '@/pages/LoginPage'

const login = vi.fn()
const authState = {
  user: null as null,
  bootstrapping: false,
  isAuthenticated: false,
  googleOAuthAvailable: false,
  registrationStatus: {
    mode: 'closed' as const,
    configured_mode: 'closed' as const,
    registration_available: false,
    requires_invitation: false,
    requires_email_verification: false,
    email_delivery_configured: false,
  },
  passwordResetAvailable: false,
  login,
  register: vi.fn(),
  logout: vi.fn(),
}

vi.mock('@/services/auth/AuthProvider', () => ({
  useAuth: () => authState,
}))

describe('LoginPage validation', () => {
  beforeEach(() => {
    login.mockReset()
    vi.stubEnv('VITE_REGISTRATION_UI_ENABLED', 'false')
    authState.passwordResetAvailable = false
    authState.registrationStatus = {
      mode: 'closed',
      configured_mode: 'closed',
      registration_available: false,
      requires_invitation: false,
      requires_email_verification: false,
      email_delivery_configured: false,
    }
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('does not call login() when email and password are empty', async () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: /Enter Studio/i }))

    expect(await screen.findByText(/Email is required/i)).toBeInTheDocument()
    expect(screen.getByText(/Password is required/i)).toBeInTheDocument()
    expect(login).not.toHaveBeenCalled()
  })

  it('does not call login() for invalid email', async () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    )

    fireEvent.change(screen.getByLabelText(/^Email$/i), { target: { value: 'bad' } })
    fireEvent.change(screen.getByLabelText(/^Password$/i), { target: { value: 'secret123' } })
    fireEvent.click(screen.getByRole('button', { name: /Enter Studio/i }))

    expect(await screen.findByText(/valid email/i)).toBeInTheDocument()
    expect(login).not.toHaveBeenCalled()
  })

  it('hides Create account when registration is closed (production default)', () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    )
    expect(screen.queryByRole('link', { name: /create account/i })).not.toBeInTheDocument()
  })

  it('hides Forgot password when reset is unavailable', () => {
    authState.passwordResetAvailable = false
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    )
    expect(screen.queryByRole('link', { name: /forgot password/i })).not.toBeInTheDocument()
  })

  it('shows Forgot password when backend reports available', () => {
    authState.passwordResetAvailable = true
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    )
    expect(screen.getByRole('link', { name: /forgot password/i })).toHaveAttribute(
      'href',
      '/forgot-password',
    )
  })

  it('shows Create Account when backend public registration is available', () => {
    authState.registrationStatus = {
      mode: 'public',
      configured_mode: 'public',
      registration_available: true,
      requires_invitation: false,
      requires_email_verification: true,
      email_delivery_configured: true,
    }
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    )
    expect(screen.getByRole('link', { name: /create account/i })).toHaveAttribute(
      'href',
      '/register',
    )
    expect(screen.getByText(/don't have an account/i)).toBeInTheDocument()
  })

  it('calls login with trimmed email on valid submit', async () => {
    login.mockResolvedValue(undefined)
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    )

    fireEvent.change(screen.getByLabelText(/^Email$/i), {
      target: { value: '  aria@fashionrise.local  ' },
    })
    fireEvent.change(screen.getByLabelText(/^Password$/i), { target: { value: 'secret123' } })
    fireEvent.click(screen.getByRole('button', { name: /Enter Studio/i }))

    await waitFor(() => {
      expect(login).toHaveBeenCalledWith({
        email: 'aria@fashionrise.local',
        password: 'secret123',
      })
    })
  })
})
