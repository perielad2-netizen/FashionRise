import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RegisterPage } from '@/pages/RegisterPage'

const registerMock = vi.fn()
const authState = {
  user: null as null | { id: string },
  bootstrapping: false,
  isAuthenticated: false,
  login: vi.fn(),
  register: registerMock,
  logout: vi.fn(),
}

vi.mock('@/services/auth/AuthProvider', () => ({
  useAuth: () => authState,
}))

function renderRegister() {
  return render(
    <MemoryRouter initialEntries={['/register']}>
      <Routes>
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/login" element={<div>Sign in page</div>} />
        <Route path="/studio" element={<div>Studio</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('RegisterPage', () => {
  beforeEach(() => {
    registerMock.mockReset()
    authState.user = null
    authState.isAuthenticated = false
    authState.bootstrapping = false
  })

  it('links back to Sign In', () => {
    renderRegister()
    expect(screen.getByRole('link', { name: /sign in/i })).toHaveAttribute('href', '/login')
  })

  it('validates required fields without calling register', async () => {
    const user = userEvent.setup()
    renderRegister()
    await user.click(screen.getByRole('button', { name: /create account/i }))
    expect(registerMock).not.toHaveBeenCalled()
    expect(screen.getByText(/enter your email/i)).toBeInTheDocument()
  })

  it('requires matching passwords', async () => {
    const user = userEvent.setup()
    renderRegister()
    await user.type(screen.getByRole('textbox', { name: /^email$/i }), 'new@example.com')
    await user.type(screen.getByRole('textbox', { name: /^username$/i }), 'newuser')
    await user.type(document.querySelector('input[name="password"]') as HTMLElement, 'StrongPass123!')
    await user.type(document.querySelector('input[name="confirmPassword"]') as HTMLElement, 'mismatch')
    await user.type(
      screen.getByRole('textbox', { name: /invitation code/i }),
      'abcdefghijklmnopqrstuvwxyz012345',
    )
    await user.click(screen.getByRole('button', { name: /create account/i }))
    expect(registerMock).not.toHaveBeenCalled()
    expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument()
  })

  it('prevents double submit while pending', async () => {
    const user = userEvent.setup()
    let resolveRegister: (() => void) | undefined
    registerMock.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveRegister = resolve
        }),
    )
    renderRegister()
    await user.type(screen.getByRole('textbox', { name: /^email$/i }), 'new@example.com')
    await user.type(screen.getByRole('textbox', { name: /^username$/i }), 'newuser')
    await user.type(document.querySelector('input[name="password"]') as HTMLElement, 'StrongPass123!')
    await user.type(
      document.querySelector('input[name="confirmPassword"]') as HTMLElement,
      'StrongPass123!',
    )
    await user.type(
      screen.getByRole('textbox', { name: /invitation code/i }),
      'abcdefghijklmnopqrstuvwxyz012345',
    )
    const button = screen.getByRole('button', { name: /create account/i })
    await user.click(button)
    await user.click(button)
    expect(registerMock).toHaveBeenCalledTimes(1)
    resolveRegister?.()
    await waitFor(() => expect(screen.getByText('Studio')).toBeInTheDocument())
  })

  it('shows invitation error from API without retrying', async () => {
    const user = userEvent.setup()
    const { ApiError } = await import('@/services/api/client')
    registerMock.mockRejectedValueOnce(new ApiError('Invitation is not valid', 403, null))
    renderRegister()
    await user.type(screen.getByRole('textbox', { name: /^email$/i }), 'new@example.com')
    await user.type(screen.getByRole('textbox', { name: /^username$/i }), 'newuser')
    await user.type(document.querySelector('input[name="password"]') as HTMLElement, 'StrongPass123!')
    await user.type(
      document.querySelector('input[name="confirmPassword"]') as HTMLElement,
      'StrongPass123!',
    )
    await user.type(
      screen.getByRole('textbox', { name: /invitation code/i }),
      'abcdefghijklmnopqrstuvwxyz012345',
    )
    await user.click(screen.getByRole('button', { name: /create account/i }))
    expect(await screen.findByText(/invitation is not valid/i)).toBeInTheDocument()
  })
})
