import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ForgotPasswordPage } from '@/pages/ForgotPasswordPage'

const requestPasswordReset = vi.fn()

vi.mock('@/services/auth/authApi', async () => {
  const actual = await vi.importActual<typeof import('@/services/auth/authApi')>(
    '@/services/auth/authApi',
  )
  return {
    ...actual,
    requestPasswordReset: (...args: unknown[]) => requestPasswordReset(...args),
  }
})

const authState = {
  user: null as null,
  bootstrapping: false,
  isAuthenticated: false,
  googleOAuthAvailable: false,
  registrationStatus: null,
  passwordResetAvailable: true,
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  refreshUser: vi.fn(),
}

vi.mock('@/services/auth/AuthProvider', () => ({
  useAuth: () => authState,
}))

describe('ForgotPasswordPage', () => {
  beforeEach(() => {
    requestPasswordReset.mockReset()
    authState.passwordResetAvailable = true
  })

  it('sends opaque success copy after submit', async () => {
    requestPasswordReset.mockResolvedValue(undefined)
    render(
      <MemoryRouter>
        <ForgotPasswordPage />
      </MemoryRouter>,
    )
    fireEvent.change(screen.getByLabelText(/^Email$/i), {
      target: { value: 'aria@fashionrise.local' },
    })
    fireEvent.click(screen.getByRole('button', { name: /send reset link/i }))
    await waitFor(() => {
      expect(requestPasswordReset).toHaveBeenCalledWith('aria@fashionrise.local')
    })
    expect(await screen.findByText(/if an account exists/i)).toBeInTheDocument()
  })

  it('explains when reset is unavailable', () => {
    authState.passwordResetAvailable = false
    render(
      <MemoryRouter>
        <ForgotPasswordPage />
      </MemoryRouter>,
    )
    expect(screen.getByText(/not available on this environment/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /send reset link/i })).not.toBeInTheDocument()
  })
})
