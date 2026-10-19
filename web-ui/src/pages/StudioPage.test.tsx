import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { StudioPage } from '@/pages/StudioPage'

vi.mock('@/services/auth/AuthProvider', () => ({
  useAuth: () => ({
    user: { id: 'u1', username: 'demo' },
    logout: vi.fn(),
    isAuthenticated: true,
    bootstrapping: false,
  }),
}))

vi.mock('@/components/studio/DrawingCanvas', () => ({
  DrawingCanvas: () => <div data-testid="drawing-canvas" />,
}))

vi.mock('@/lib/draftPersistence', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/draftPersistence')>()
  return {
    ...actual,
    restoreStudioDraft: async () => ({
      designId: null,
      document: {
        schema: 'fashionrise.studio.draft.v1',
        strokes: [],
        model: 'female',
        customReferenceUrl: null,
        customReferenceKey: null,
        brush: { sizeId: 'thin', opacity: 1, color: '#1C1C1E' },
        dimmed: false,
        clientRevision: 1,
        updatedAt: '2026-10-19T00:00:00.000Z',
      },
      syncedRevision: null,
      conflict: null,
      notice: null,
    }),
    persistStudioDraft: async ({
      designId,
      document,
    }: {
      designId: string | null
      document: unknown
    }) => ({
      ok: true as const,
      designId: designId ?? 'design-1',
      document,
      fingerprint: 'fp',
      syncedRevision: 1,
      localPersisted: true,
    }),
    persistLocalRecovery: async () => ({ ok: true as const }),
  }
})

vi.mock('@/lib/localDraftStore', () => ({
  readLocalDraft: async () => null,
  writeLocalDraft: async () => ({ ok: true, wrote: true }),
  clearLocalDraft: async () => undefined,
  readStoredDesignId: () => null,
  writeStoredDesignId: () => undefined,
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

  it('renders approved shell chrome with truthful save status', async () => {
    render(
      <MemoryRouter>
        <StudioPage />
      </MemoryRouter>,
    )

    expect(
      screen.getByText((_, node) => node?.tagName === 'P' && node.textContent === 'FashionRise'),
    ).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /new design/i })).toBeInTheDocument()
    expect(await screen.findByText(/ready|saved|restoring/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/creator workspace/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/model library/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/settings inspector/i)).toBeInTheDocument()
    expect(screen.getByTestId('drawing-canvas')).toBeInTheDocument()
    expect(screen.queryByText(/auto save/i)).not.toBeInTheDocument()
  })
})
