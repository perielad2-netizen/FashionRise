import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LoginPage } from '@/pages/LoginPage'

const login = vi.fn()

vi.mock('@/services/auth/AuthProvider', () => ({
  useAuth: () => ({
    user: null,
    bootstrapping: false,
    isAuthenticated: false,
    login,
    register: vi.fn(),
    logout: vi.fn(),
  }),
}))

describe('LoginPage validation', () => {
  beforeEach(() => {
    login.mockReset()
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

  it('hides Create account when registration UI is disabled (production default)', () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    )
    expect(screen.queryByRole('link', { name: /create account/i })).not.toBeInTheDocument()
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
