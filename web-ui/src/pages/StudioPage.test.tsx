import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { StudioPage } from '@/pages/StudioPage'
import type { Stroke } from '@/lib/strokes'

vi.mock('@/config/magicUi', () => ({
  // Keep Studio chrome “Soon” notices deterministic regardless of local .env.
  isMagicUiEnabled: () => false,
}))

vi.mock('@/services/auth/AuthProvider', () => ({
  useAuth: () => ({
    user: { id: 'u1', username: 'demo' },
    logout: vi.fn(),
    isAuthenticated: true,
    bootstrapping: false,
  }),
}))

vi.mock('@/components/studio/DrawingCanvas', () => ({
  DrawingCanvas: ({ onStrokeComplete }: { onStrokeComplete: (stroke: Stroke) => void }) => (
    <div data-testid="drawing-canvas">
      <button
        type="button"
        onClick={() =>
          onStrokeComplete({
            id: `s-${Math.random()}`,
            tool: 'draw',
            points: [100, 100, 0.5, 140, 120, 0.5, 180, 140, 0.5],
            color: '#1C1C1E',
            size: 1.75,
            opacity: 1,
          })
        }
      >
        Mock stroke
      </button>
    </div>
  ),
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

const viewportState = { width: 1440, height: 900 }
const mediaListeners = new Set<() => void>()

function queryMatches(query: string) {
  const clauses = [...query.matchAll(/\((min|max)-(width|height):\s*(\d+)px\)/g)]
  if (clauses.length === 0) return false
  return clauses.every(([, bound, axis, px]) => {
    const value = viewportState[axis as 'width' | 'height']
    return bound === 'max' ? value <= Number(px) : value >= Number(px)
  })
}

/** matchMedia mock whose `matches` follows the current viewport, so rotations fire `change`. */
function mockViewport(width: number, height = 900) {
  viewportState.width = width
  viewportState.height = height
  mediaListeners.clear()
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      get matches() {
        return queryMatches(query)
      },
      media: query,
      addEventListener: (_: string, cb: () => void) => mediaListeners.add(cb),
      removeEventListener: (_: string, cb: () => void) => mediaListeners.delete(cb),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }),
  })
  Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: width })
  Object.defineProperty(window, 'innerHeight', { writable: true, configurable: true, value: height })
}

function rotateTo(width: number, height: number) {
  act(() => {
    viewportState.width = width
    viewportState.height = height
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: width })
    Object.defineProperty(window, 'innerHeight', { writable: true, configurable: true, value: height })
    for (const listener of [...mediaListeners]) listener()
    window.dispatchEvent(new Event('resize'))
  })
}

function dockButton(name: string) {
  return within(screen.getByLabelText('Studio panels')).getByRole('button', { name, hidden: true })
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
    { width: 1024, height: 550 },
    { width: 1180, height: 600 },
    { width: 1440, height: 900 },
  ] as const

  for (const viewport of viewports) {
    it(`shows and dismisses Magic, Settings, and Back at ${viewport.width}×${viewport.height}`, async () => {
      mockViewport(viewport.width, viewport.height)
      await openStudio()

      const settingsDock = dockButton('Settings')
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

function settingsInspector() {
  return screen.getByLabelText(/settings inspector/i)
}

function brushSheet() {
  return screen.queryByRole('dialog', { name: 'Brush settings sheet' })
}

describe('WEB-V2.3 brush controls and landscape layout', () => {
  it('has no floating brush window on desktop; Settings keeps size and opacity', async () => {
    mockViewport(1440, 900)
    await openStudio()

    expect(screen.queryByLabelText('Brush settings')).not.toBeInTheDocument()
    expect(brushSheet()).not.toBeInTheDocument()
    expect(screen.getAllByRole('slider', { name: 'Brush size' })).toHaveLength(1)
    expect(screen.getAllByRole('slider', { name: 'Brush opacity' })).toHaveLength(1)
    const size = within(settingsInspector()).getByRole('slider', { name: 'Brush size' })
    fireEvent.change(size, { target: { value: '6.5' } })
    expect(
      within(settingsInspector()).getByLabelText('Brush size in pixels'),
    ).toHaveValue('6.5')
    const opacity = within(settingsInspector()).getByRole('slider', { name: 'Brush opacity' })
    fireEvent.change(opacity, { target: { value: '40' } })
    expect(within(settingsInspector()).getByText('40%')).toBeInTheDocument()
  })

  it('keeps brush size and opacity in the Settings column at 1180×600', async () => {
    mockViewport(1180, 600)
    await openStudio()

    expect(screen.queryByLabelText('Brush settings')).not.toBeInTheDocument()
    expect(within(settingsInspector()).getByRole('slider', { name: 'Brush size' })).toBeInTheDocument()
    expect(within(settingsInspector()).getByRole('slider', { name: 'Brush opacity' })).toBeInTheDocument()
  })

  it('opens a dismissible Brush sheet from the dock at 1024×550', async () => {
    mockViewport(1024, 550)
    await openStudio()
    expect(brushSheet()).not.toBeInTheDocument()

    fireEvent.click(dockButton('Brush panel'))
    const sheet = brushSheet()!
    expect(sheet).toBeVisible()
    fireEvent.change(within(sheet).getByRole('slider', { name: 'Brush size' }), {
      target: { value: '6.5' },
    })
    fireEvent.change(within(sheet).getByRole('slider', { name: 'Brush opacity' }), {
      target: { value: '55' },
    })
    expect(
      within(settingsInspector()).getByLabelText('Brush size in pixels'),
    ).toHaveValue('6.5')
    expect(within(settingsInspector()).getByText('55%')).toBeInTheDocument()

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(brushSheet()).not.toBeInTheDocument()

    fireEvent.click(dockButton('Brush panel'))
    fireEvent.click(within(brushSheet()!).getByRole('button', { name: 'Done' }))
    expect(brushSheet()).not.toBeInTheDocument()

    fireEvent.click(dockButton('Brush panel'))
    fireEvent.click(screen.getByRole('button', { name: 'Close brush panel' }))
    expect(brushSheet()).not.toBeInTheDocument()
  })

  for (const [width, height] of [
    [1024, 550],
    [1180, 600],
    [1440, 900],
  ] as const) {
    it(`Settings has no Generate with AI footer; header Magic Soon still works at ${width}×${height}`, async () => {
      mockViewport(width, height)
      await openStudio()

      // WEB-V4I: obsolete Settings "Generate with AI — Soon" footer removed.
      expect(
        within(settingsInspector()).queryByRole('button', {
          name: /Generate with AI/i,
          hidden: true,
        }),
      ).toBeNull()

      // Real Magic entry remains in the Studio header (Soon when magic UI is disabled).
      const magic = screen.getByRole('button', { name: /^Magic/i })
      expect(magic).toHaveTextContent(/Soon/i)
      fireEvent.click(magic)
      const notice = noticeFor(/later milestone/i)
      expect(notice).toBeVisible()
      expect(settingsInspector().contains(notice)).toBe(false)
      fireEvent.click(screen.getByRole('button', { name: 'Got it' }))
      expect(screen.queryByRole('status', { name: /later milestone/i })).not.toBeInTheDocument()
    })
  }

  it('keeps the drawing, brush settings, and canvas through orientation and browser-chrome changes', async () => {
    mockViewport(768, 1024)
    await openStudio()
    const canvas = screen.getByTestId('drawing-canvas')

    fireEvent.click(screen.getByRole('button', { name: 'Mock stroke' }))
    for (const undo of screen.getAllByRole('button', { name: 'Undo' })) expect(undo).toBeEnabled()

    fireEvent.click(dockButton('Brush panel'))
    fireEvent.change(within(brushSheet()!).getByRole('slider', { name: 'Brush size' }), {
      target: { value: '6.5' },
    })

    rotateTo(1024, 550)
    expect(brushSheet()).toBeVisible()

    rotateTo(1024, 700)
    rotateTo(1180, 600)
    expect(brushSheet()).not.toBeInTheDocument()
    expect(screen.getByTestId('drawing-canvas')).toBe(canvas)
    expect(
      within(settingsInspector()).getByLabelText('Brush size in pixels'),
    ).toHaveValue('6.5')

    rotateTo(1440, 900)
    rotateTo(768, 1024)
    expect(screen.getByTestId('drawing-canvas')).toBe(canvas)
    for (const undo of screen.getAllByRole('button', { name: 'Undo' })) expect(undo).toBeEnabled()
    expect(
      within(settingsInspector()).getByLabelText('Brush size in pixels'),
    ).toHaveValue('6.5')
    expect(screen.queryByText(/save failed/i)).not.toBeInTheDocument()

    fireEvent.click(screen.getAllByRole('button', { name: 'Undo' })[0]!)
    for (const undo of screen.getAllByRole('button', { name: 'Undo' })) expect(undo).toBeDisabled()
  })

  it('removes the cropped sidebar promo and keeps navigation controls', async () => {
    mockViewport(1440, 900)
    await openStudio()

    expect(screen.queryByText(/fashion is your superpower/i)).not.toBeInTheDocument()
    const nav = screen.getByRole('navigation', { name: 'FashionRise' })
    expect(nav.querySelector('img')).toBeNull()
    expect(within(nav).getByRole('button', { name: 'Create' })).toHaveAttribute('aria-current', 'page')
    for (const label of ['Home', 'Design Book', 'Discover', 'My Looks']) {
      expect(within(nav).getByRole('button', { name: label })).toBeDisabled()
    }
  })
})
