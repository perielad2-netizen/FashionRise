import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { VerifyEmailPage } from '@/pages/VerifyEmailPage'

const verifyEmail = vi.fn()
const refreshUser = vi.fn()
const navigate = vi.fn()

vi.mock('@/services/auth/authApi', () => ({
  verifyEmail: (...args: unknown[]) => verifyEmail(...args),
}))

vi.mock('@/services/auth/AuthProvider', () => ({
  useAuth: () => ({
    isAuthenticated: false,
    bootstrapping: false,
    refreshUser,
  }),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => navigate,
  }
})

describe('VerifyEmailPage', () => {
  beforeEach(() => {
    verifyEmail.mockReset()
    refreshUser.mockReset()
    navigate.mockReset()
    window.history.replaceState(null, '', '/verify-email')
  })

  afterEach(() => {
    window.history.replaceState(null, '', '/')
  })

  it('does not auto-verify on load (scanner-safe); requires Confirm', async () => {
    window.history.replaceState(null, '', '/verify-email#token=abcdefghijklmnopqrstuvwxyz012345')
    render(
      <MemoryRouter>
        <VerifyEmailPage />
      </MemoryRouter>,
    )
    expect(await screen.findByRole('button', { name: /confirm email/i })).toBeInTheDocument()
    expect(verifyEmail).not.toHaveBeenCalled()
    // Fragment cleared from history immediately.
    expect(window.location.hash).toBe('')
  })

  it('POSTs token only after explicit confirm', async () => {
    verifyEmail.mockResolvedValue({
      user: { id: 'u1' },
      tokens: { accessToken: 'a', refreshToken: 'r' },
    })
    refreshUser.mockResolvedValue(undefined)
    window.history.replaceState(null, '', '/verify-email#token=abcdefghijklmnopqrstuvwxyz012345')
    render(
      <MemoryRouter>
        <VerifyEmailPage />
      </MemoryRouter>,
    )
    fireEvent.click(await screen.findByRole('button', { name: /confirm email/i }))
    await waitFor(() => {
      expect(verifyEmail).toHaveBeenCalledWith('abcdefghijklmnopqrstuvwxyz012345')
    })
  })

  it('rejects query-string tokens (access-log leakage) without consuming them', async () => {
    window.history.replaceState(
      null,
      '',
      '/verify-email?token=abcdefghijklmnopqrstuvwxyz012345',
    )
    render(
      <MemoryRouter>
        <VerifyEmailPage />
      </MemoryRouter>,
    )
    expect(await screen.findByText(/unsafe format/i)).toBeInTheDocument()
    expect(verifyEmail).not.toHaveBeenCalled()
    expect(window.location.search).not.toContain('token=')
  })
})
