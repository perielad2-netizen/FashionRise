import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ResetPasswordPage } from '@/pages/ResetPasswordPage'

const resetPassword = vi.fn()
const navigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => navigate,
    Navigate: ({ to }: { to: string }) => <div data-testid="navigate" data-to={to} />,
  }
})

vi.mock('@/services/auth/authApi', async () => {
  const actual = await vi.importActual<typeof import('@/services/auth/authApi')>(
    '@/services/auth/authApi',
  )
  return {
    ...actual,
    resetPassword: (...args: unknown[]) => resetPassword(...args),
  }
})

const authState = {
  user: null as null | { id: string; username: string },
  bootstrapping: false,
  isAuthenticated: false,
  googleOAuthAvailable: false,
  registrationStatus: null,
  passwordResetAvailable: true,
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  refreshUser: vi.fn().mockResolvedValue(undefined),
}

vi.mock('@/services/auth/AuthProvider', () => ({
  useAuth: () => authState,
}))

describe('ResetPasswordPage', () => {
  beforeEach(() => {
    resetPassword.mockReset()
    navigate.mockReset()
    authState.passwordResetAvailable = true
    authState.isAuthenticated = false
    authState.user = null
    window.history.replaceState(null, '', '/reset-password')
  })

  it('requires confirm click with matching passwords from hash token', async () => {
    resetPassword.mockResolvedValue({ user: { id: 'u1' }, tokens: {} })
    window.history.replaceState(null, '', '/reset-password#token=abcdefghijklmnopqrstuvwxyz012345')
    render(
      <MemoryRouter>
        <ResetPasswordPage />
      </MemoryRouter>,
    )
    expect(window.location.hash).toBe('')
    fireEvent.change(screen.getByLabelText(/^New password$/i), {
      target: { value: 'newpass12' },
    })
    fireEvent.change(screen.getByLabelText(/^Confirm password$/i), {
      target: { value: 'newpass12' },
    })
    fireEvent.click(screen.getByRole('button', { name: /save password/i }))
    await waitFor(() => {
      expect(resetPassword).toHaveBeenCalledWith(
        'abcdefghijklmnopqrstuvwxyz012345',
        'newpass12',
      )
    })
    expect(navigate).toHaveBeenCalledWith('/studio/home', { replace: true })
  })

  it('rejects query-string tokens', () => {
    window.history.replaceState(
      null,
      '',
      '/reset-password?token=abcdefghijklmnopqrstuvwxyz012345',
    )
    render(
      <MemoryRouter>
        <ResetPasswordPage />
      </MemoryRouter>,
    )
    expect(screen.getByText(/unsafe format/i)).toBeInTheDocument()
    expect(resetPassword).not.toHaveBeenCalled()
  })

  it('shows the password form when already authenticated if a reset token is present', () => {
    authState.isAuthenticated = true
    authState.user = { id: 'a1', username: 'account_a' }
    window.history.replaceState(null, '', '/reset-password#token=abcdefghijklmnopqrstuvwxyz012345')
    render(
      <MemoryRouter>
        <ResetPasswordPage />
      </MemoryRouter>,
    )
    expect(screen.queryByTestId('navigate')).toBeNull()
    expect(screen.getByRole('button', { name: /save password/i })).toBeInTheDocument()
    expect(screen.getByText(/signed in as/i)).toBeInTheDocument()
    expect(screen.getByText('account_a')).toBeInTheDocument()
    expect(resetPassword).not.toHaveBeenCalled()
  })

  it('does not redeem on open — only Save password POSTs', () => {
    window.history.replaceState(null, '', '/reset-password#token=abcdefghijklmnopqrstuvwxyz012345')
    render(
      <MemoryRouter>
        <ResetPasswordPage />
      </MemoryRouter>,
    )
    expect(resetPassword).not.toHaveBeenCalled()
  })
})
