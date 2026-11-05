import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { ProtectedRoute } from '@/components/layout/ProtectedRoute'

vi.mock('@/services/auth/AuthProvider', () => ({
  useAuth: vi.fn(),
}))

import { useAuth } from '@/services/auth/AuthProvider'

const mockedUseAuth = vi.mocked(useAuth)

describe('ProtectedRoute', () => {
  it('redirects unauthenticated users to login', () => {
    mockedUseAuth.mockReturnValue({
      user: null,
      bootstrapping: false,
      isAuthenticated: false,
      login: vi.fn(),
      logout: vi.fn(),
    })

    render(
      <MemoryRouter initialEntries={['/studio']}>
        <Routes>
          <Route
            path="/studio"
            element={
              <ProtectedRoute>
                <div>Studio secret</div>
              </ProtectedRoute>
            }
          />
          <Route path="/login" element={<div>Login page</div>} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByText('Login page')).toBeInTheDocument()
    expect(screen.queryByText('Studio secret')).not.toBeInTheDocument()
  })

  it('renders children when authenticated', () => {
    mockedUseAuth.mockReturnValue({
      user: {
        id: '1',
        email: 'a@b.com',
        username: 'aria',
        is_active: true,
        is_admin: false,
        created_at: '',
      },
      bootstrapping: false,
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
    })

    render(
      <MemoryRouter initialEntries={['/studio']}>
        <Routes>
          <Route
            path="/studio"
            element={
              <ProtectedRoute>
                <div>Studio secret</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByText('Studio secret')).toBeInTheDocument()
  })
})
