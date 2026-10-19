import { fireEvent, render, screen, within } from '@testing-library/react'
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

function mockViewport(width: number) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => {
      const max = /max-width:\s*(\d+)px/.exec(query)
      const matches = max ? width <= Number(max[1]) : false
      return {
        matches,
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }
    },
  })
  Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: width })
}

async function openStudio() {
  render(
    <MemoryRouter>
      <StudioPage />
    </MemoryRouter>,
  )
  expect(await screen.findByText(/ready|saved|restoring/i)).toBeInTheDocument()
}

function noticeFor(text: RegExp) {
  return screen.getByRole('status', { name: text })
}

describe('Studio beta notices stay outside Settings', () => {
  const viewports = [
    { width: 390, height: 844 },
    { width: 768, height: 1024 },
    { width: 1440, height: 900 },
  ] as const

  for (const viewport of viewports) {
    it(`shows and dismisses Magic, Settings, and Back at ${viewport.width}×${viewport.height}`, async () => {
      mockViewport(viewport.width)
      Object.defineProperty(window, 'innerHeight', {
        writable: true,
        configurable: true,
        value: viewport.height,
      })
      await openStudio()

      const settingsDock = within(screen.getByLabelText('Studio panels')).getByRole('button', {
        name: 'Settings',
        hidden: true,
      })
      expect(settingsDock.className).not.toMatch(/dockActive/)

      fireEvent.click(screen.getByRole('button', { name: /^Magic/i }))
      const magic = noticeFor(/later milestone/i)
      expect(magic).toBeVisible()
      expect(screen.getByLabelText(/settings inspector/i).contains(magic)).toBe(false)
      expect(screen.getAllByRole('status', { name: /later milestone/i })).toHaveLength(1)
      fireEvent.click(screen.getByRole('button', { name: 'Got it' }))
      expect(screen.queryByRole('status', { name: /later milestone/i })).not.toBeInTheDocument()

      fireEvent.click(screen.getByRole('button', { name: 'Settings, coming later' }))
      const settingsNotice = noticeFor(/Settings — coming later/i)
      expect(settingsNotice).toBeVisible()
      expect(screen.getByLabelText(/settings inspector/i).contains(settingsNotice)).toBe(false)
      expect(settingsDock.className).not.toMatch(/dockActive/)
      fireEvent.click(screen.getByRole('button', { name: 'Got it' }))
      expect(screen.queryByRole('status', { name: /Settings — coming later/i })).not.toBeInTheDocument()

      fireEvent.click(screen.getByRole('button', { name: 'Home, coming later' }))
      const home = noticeFor(/Home — coming later/i)
      expect(home).toBeVisible()
      expect(screen.getByLabelText(/settings inspector/i).contains(home)).toBe(false)
      fireEvent.click(screen.getByRole('button', { name: /^Magic/i }))
      expect(screen.queryByRole('status', { name: /Home — coming later/i })).not.toBeInTheDocument()
      expect(noticeFor(/later milestone/i)).toBeVisible()
      expect(screen.getAllByRole('status', { name: /later milestone/i })).toHaveLength(1)
      fireEvent.click(screen.getByRole('button', { name: 'Got it' }))
      expect(screen.queryByRole('status', { name: /later milestone/i })).not.toBeInTheDocument()
    })
  }
})
