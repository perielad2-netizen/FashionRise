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

vi.mock('@/lib/draftPersistence', () => ({
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
    conflict: null,
    notice: null,
  }),
  persistStudioDraft: async ({ designId, document }: { designId: string | null; document: unknown }) => ({
    designId: designId ?? 'design-1',
    document,
    fingerprint: 'fp',
  }),
  documentFromEditorState: (input: {
    prev: { clientRevision?: number }
    strokes: unknown
    model: unknown
    customReferenceUrl: unknown
    customReferenceKey: unknown
    sizeId: unknown
    opacity: unknown
    color: unknown
    dimmed: unknown
  }) => ({
    schema: 'fashionrise.studio.draft.v1',
    strokes: input.strokes,
    model: input.model,
    customReferenceUrl: input.customReferenceUrl,
    customReferenceKey: input.customReferenceKey,
    brush: { sizeId: input.sizeId, opacity: input.opacity, color: input.color },
    dimmed: input.dimmed,
    clientRevision: Number(input.prev.clientRevision ?? 1) + 1,
    updatedAt: new Date().toISOString(),
  }),
}))

vi.mock('@/lib/localDraftStore', () => ({
  readLocalDraft: async () => null,
  writeLocalDraft: async () => undefined,
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

    expect(screen.getByText('FashionRise')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /new design/i })).toBeInTheDocument()
    expect(await screen.findByText(/ready|saved|restoring/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/creator workspace/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/model library/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/settings inspector/i)).toBeInTheDocument()
    expect(screen.getByTestId('drawing-canvas')).toBeInTheDocument()
    expect(screen.queryByText(/auto save/i)).not.toBeInTheDocument()
  })
})
