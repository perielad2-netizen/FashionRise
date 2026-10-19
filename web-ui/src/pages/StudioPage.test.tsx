import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { StudioPage } from '@/pages/StudioPage'

vi.mock('@/services/auth/AuthProvider', () => ({
  useAuth: () => ({
    user: { username: 'demo' },
    logout: vi.fn(),
    isAuthenticated: true,
    bootstrapping: false,
  }),
}))

vi.mock('@/components/studio/DrawingCanvas', () => ({
  DrawingCanvas: () => <div data-testid="drawing-canvas" />,
}))

describe('StudioPage WEB-V2 shell', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: (query: string) => ({
        matches: false,
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }),
    })
  })

  it('renders approved shell chrome with unsaved session status', () => {
    render(
      <MemoryRouter>
        <StudioPage />
      </MemoryRouter>,
    )

    expect(screen.getByText('FashionRise')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /new design/i })).toBeInTheDocument()
    expect(screen.getByText(/unsaved session/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/creator workspace/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/model library/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/settings inspector/i)).toBeInTheDocument()
    expect(screen.getByTestId('drawing-canvas')).toBeInTheDocument()
    expect(screen.queryByText(/auto save/i)).not.toBeInTheDocument()
  })
})
