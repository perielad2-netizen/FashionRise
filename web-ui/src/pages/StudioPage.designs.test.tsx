import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { StudioPage } from '@/pages/StudioPage'
import { draftContentFingerprint, type StudioDraftDocument } from '@/lib/draftDocument'
import type { SavedDesignRecord } from '@/lib/savedDesign'
import type { Stroke } from '@/lib/strokes'

const mocks = vi.hoisted(() => ({
  restoreStudioDraft: vi.fn(),
  persistStudioDraft: vi.fn(),
  persistLocalRecovery: vi.fn(),
  saveDesignSnapshot: vi.fn(),
  listSavedDesigns: vi.fn(),
  fetchSavedDesign: vi.fn(),
  listMyDesigns: vi.fn(),
  exportSketchPng: vi.fn(),
  downloadBlob: vi.fn(),
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
  DrawingCanvas: ({
    strokes,
    onStrokeComplete,
  }: {
    strokes: Stroke[]
    onStrokeComplete: (stroke: Stroke) => void
  }) => (
    <div data-testid="drawing-canvas">
      <output data-testid="stroke-ids">{strokes.map((s) => s.id).join(',')}</output>
      <button
        type="button"
        onClick={() =>
          onStrokeComplete({
            id: `new-${strokes.length}`,
            tool: 'draw',
            points: [100, 100, 0.5, 140, 120, 0.5],
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
    restoreStudioDraft: mocks.restoreStudioDraft,
    persistStudioDraft: mocks.persistStudioDraft,
    persistLocalRecovery: mocks.persistLocalRecovery,
  }
})

vi.mock('@/lib/localDraftStore', () => ({
  readLocalDraft: async () => null,
  writeLocalDraft: async () => ({ ok: true, wrote: true }),
  replaceLocalDraft: async () => ({ ok: true }),
  clearLocalDraft: async () => undefined,
  readStoredDesignId: () => null,
  writeStoredDesignId: () => undefined,
}))

vi.mock('@/services/savedDesignsApi', () => ({
  saveDesignSnapshot: mocks.saveDesignSnapshot,
  listSavedDesigns: mocks.listSavedDesigns,
  fetchSavedDesign: mocks.fetchSavedDesign,
}))

vi.mock('@/services/designsApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/designsApi')>()
  return { ...actual, listMyDesigns: mocks.listMyDesigns }
})

vi.mock('@/lib/exportCanvas', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/exportCanvas')>()
  return { ...actual, exportSketchPng: mocks.exportSketchPng, downloadBlob: mocks.downloadBlob }
})

vi.mock('@/lib/designPreview', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/designPreview')>()
  class FakeRenderer {
    request() {
      return Promise.resolve(null)
    }
    release() {}
    dispose() {}
  }
  return { ...actual, PreviewRenderer: FakeRenderer }
})

const STROKE: Stroke = {
  id: 'restored-1',
  tool: 'draw',
  points: [10, 10, 0.5, 20, 20, 0.5],
  color: '#1C1C1E',
  size: 1.75,
  opacity: 1,
}

function workingDoc(overrides: Partial<StudioDraftDocument> = {}): StudioDraftDocument {
  return {
    schema: 'fashionrise.studio.draft.v1',
    strokes: [STROKE],
    model: 'female',
    customReferenceUrl: null,
    customReferenceKey: null,
    brush: { sizeId: 'thin', opacity: 1, color: '#1C1C1E' },
    dimmed: false,
    clientRevision: 3,
    updatedAt: '2026-10-20T00:00:00.000Z',
    ...overrides,
  }
}

const RECORD: SavedDesignRecord = {
  id: 'saved-1',
  title: 'Evening gown',
  savedAt: '2026-10-20T10:00:00.000Z',
  createdAt: '2026-10-20T10:00:00.000Z',
  saveRequestId: 'req-1',
  snapshot: {
    strokes: [
      { id: 'snap-1', tool: 'draw', points: [1, 2, 0.5], color: '#D63384', size: 3.5, opacity: 0.7 },
      { id: 'snap-2', tool: 'erase', points: [3, 4, 0.5], color: '#1C1C1E', size: 7, opacity: 1 },
    ],
    model: 'male',
    brush: { sizeId: 'medium', opacity: 0.7, color: '#D63384' },
    dimmed: true,
  },
}

function cleanRestore(doc = workingDoc()) {
  mocks.restoreStudioDraft.mockResolvedValue({
    designId: 'draft-1',
    document: doc,
    syncedRevision: doc.clientRevision,
    conflict: null,
    notice: null,
  })
}

function okPersist({ document, designId }: { document: StudioDraftDocument; designId: string | null }) {
  return Promise.resolve({
    ok: true as const,
    designId: designId ?? 'draft-1',
    document,
    fingerprint: draftContentFingerprint({ ...document, customReferenceUrl: null, customReferenceKey: null }),
    syncedRevision: document.clientRevision,
    localPersisted: true,
  })
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/studio/*" element={<StudioPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

async function ready() {
  await screen.findByText('Saved')
}

function strokeIds() {
  return screen.getByTestId('stroke-ids').textContent
}

beforeEach(() => {
  Object.values(mocks).forEach((m) => m.mockReset())
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
  cleanRestore()
  mocks.persistStudioDraft.mockImplementation(okPersist)
  mocks.persistLocalRecovery.mockResolvedValue({ ok: true })
  mocks.listSavedDesigns.mockResolvedValue({ designs: [RECORD], damaged: [] })
  mocks.fetchSavedDesign.mockResolvedValue({ ok: true, record: RECORD })
  mocks.listMyDesigns.mockResolvedValue([])
})

afterEach(() => {
  vi.useRealTimers()
})

describe('Save as design', () => {
  it('saves an independent snapshot and reports success only after acknowledgement', async () => {
    let resolveSave!: (v: unknown) => void
    mocks.saveDesignSnapshot.mockReturnValue(new Promise((r) => (resolveSave = r)))
    renderAt('/studio')
    await ready()

    fireEvent.click(screen.getByRole('button', { name: 'Save design' }))
    const dialog = screen.getByRole('dialog', { name: 'Save as design' })
    const input = within(dialog).getByLabelText('Title')
    expect(input).toHaveFocus()
    fireEvent.change(input, { target: { value: '  Evening   gown ' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Save design' }))
    fireEvent.click(within(dialog).getByRole('button', { name: 'Saving…' }))
    fireEvent.submit(dialog)

    expect(mocks.saveDesignSnapshot).toHaveBeenCalledTimes(1)
    const req = mocks.saveDesignSnapshot.mock.calls[0]![0]
    expect(req).toMatchObject({ ownerId: 'u1', title: 'Evening gown', previousAttemptUncertain: false })
    expect(req.snapshot.strokes).toEqual([STROKE])
    expect(screen.queryByRole('status', { name: /to My Designs/ })).toBeNull()

    await act(async () => {
      resolveSave({ ok: true, recovered: false, record: { ...RECORD, title: 'Evening gown' } })
    })
    expect(screen.queryByRole('dialog', { name: 'Save as design' })).toBeNull()
    expect(screen.getByRole('status', { name: /Saved “Evening gown” to My Designs/ })).toBeInTheDocument()
    // The working draft was not written by Save as design.
    expect(mocks.persistStudioDraft).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Mock stroke' }))
    expect(req.snapshot.strokes).toHaveLength(1)
  })

  it('retries with the same request id after an uncertain failure', async () => {
    mocks.saveDesignSnapshot
      .mockResolvedValueOnce({ ok: false, error: 'Could not reach FashionRise.', outcomeUncertain: true })
      .mockResolvedValueOnce({ ok: true, recovered: true, record: RECORD })
    renderAt('/studio')
    await ready()
    fireEvent.click(screen.getByRole('button', { name: 'Save design' }))
    const dialog = screen.getByRole('dialog', { name: 'Save as design' })
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Save design' }))
    })
    expect(within(dialog).getByRole('alert')).toHaveTextContent('Could not reach FashionRise.')
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Try again' }))
    })
    const [first, second] = mocks.saveDesignSnapshot.mock.calls.map((c) => c[0])
    expect(second.saveRequestId).toBe(first.saveRequestId)
    expect(second.previousAttemptUncertain).toBe(true)
    expect(second.snapshot).toBe(first.snapshot)
    expect(screen.queryByRole('dialog', { name: 'Save as design' })).toBeNull()
  })

  it('validates the title and keeps the dialog open', async () => {
    renderAt('/studio')
    await ready()
    fireEvent.click(screen.getByRole('button', { name: 'Save design' }))
    const dialog = screen.getByRole('dialog', { name: 'Save as design' })
    fireEvent.change(within(dialog).getByLabelText('Title'), { target: { value: '   ' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Save design' }))
    expect(within(dialog).getByRole('alert')).toHaveTextContent('Enter a title')
    expect(mocks.saveDesignSnapshot).not.toHaveBeenCalled()
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByRole('dialog', { name: 'Save as design' })).toBeNull()
  })

  it('does not open for an empty canvas', async () => {
    cleanRestore(workingDoc({ strokes: [] }))
    renderAt('/studio')
    await ready()
    fireEvent.click(screen.getByRole('button', { name: 'Save design' }))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.getByRole('status', { name: /Draw something/ })).toBeInTheDocument()
  })
})

describe('Export PNG', () => {
  it('exports the authoritative document and downloads a PNG', async () => {
    cleanRestore(workingDoc({ dimmed: true }))
    const blob = new Blob(['png'], { type: 'image/png' })
    mocks.exportSketchPng.mockResolvedValue({ blob, referenceIncluded: true })
    renderAt('/studio')
    await ready()
    fireEvent.click(screen.getByRole('button', { name: 'More' }))
    await act(async () => {
      fireEvent.click(screen.getByRole('menuitem', { name: 'Export PNG' }))
    })
    expect(mocks.exportSketchPng).toHaveBeenCalledWith({
      strokes: [STROKE],
      fills: [],
      // Legacy model id must keep original croquis geometry.
      referenceUrl: '/models/female_model.png',
      referenceOpacity: 0.4,
    })
    expect(mocks.downloadBlob).toHaveBeenCalledWith(blob, expect.stringMatching(/^fashionrise-sketch-\d{4}-\d{2}-\d{2}-\d{4}\.png$/))
    expect(screen.getByRole('status', { name: /PNG exported/ })).toBeInTheDocument()
  })

  it('reports a missing reference and failures honestly', async () => {
    mocks.exportSketchPng
      .mockResolvedValueOnce({ blob: new Blob(['x'], { type: 'image/png' }), referenceIncluded: false })
      .mockRejectedValueOnce(new Error('Canvas 2D unavailable'))
    renderAt('/studio')
    await ready()
    fireEvent.click(screen.getByRole('button', { name: 'More' }))
    await act(async () => {
      fireEvent.click(screen.getByRole('menuitem', { name: 'Export PNG' }))
    })
    expect(screen.getByRole('status', { name: /without the reference image/ })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'More' }))
    await act(async () => {
      fireEvent.click(screen.getByRole('menuitem', { name: 'Export PNG' }))
    })
    expect(screen.getByRole('status', { name: /PNG export failed/ })).toBeInTheDocument()
    expect(mocks.downloadBlob).toHaveBeenCalledTimes(1)
  })
})

describe('My Designs navigation and library', () => {
  it('is reachable from the sidebar without reactivating placeholders', async () => {
    renderAt('/studio')
    await ready()
    const nav = screen.getByRole('navigation', { name: 'FashionRise' })
    fireEvent.click(within(nav).getByRole('button', { name: 'My Designs' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'My Designs' })).toBeInTheDocument()
    expect(within(nav).getByRole('button', { name: 'My Designs' })).toHaveAttribute('aria-current', 'page')
    for (const label of ['Home', 'Design Book', 'Discover', 'My Looks']) {
      expect(within(nav).getByRole('button', { name: label })).toBeDisabled()
    }
    fireEvent.click(within(nav).getByRole('button', { name: 'Create' }))
    expect(screen.getByRole('heading', { name: 'New Design' })).toBeInTheDocument()
  })

  it('keeps the same editor mounted across screens', async () => {
    renderAt('/studio')
    await ready()
    fireEvent.click(screen.getByRole('button', { name: 'Mock stroke' }))
    fireEvent.click(screen.getByRole('button', { name: 'More' }))
    fireEvent.click(screen.getByRole('menuitem', { name: 'My Designs' }))
    expect(await screen.findByText('2 strokes')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Back to Studio' }))
    expect(strokeIds()).toBe('restored-1,new-1')
    expect(mocks.restoreStudioDraft).toHaveBeenCalledTimes(1)
  })

  it('shows the working draft separately and titles as plain text', async () => {
    const hostile = { ...RECORD, id: 'saved-x', title: '<img src=x onerror=alert(1)>' }
    mocks.listSavedDesigns.mockResolvedValue({
      designs: [hostile],
      damaged: [{ id: 'bad', title: 'Broken', createdAt: RECORD.createdAt }],
    })
    const { container } = renderAt('/studio/designs')
    await ready()
    expect(screen.getByRole('heading', { name: 'Studio working draft' })).toBeInTheDocument()
    expect(screen.getByText('Current sketch')).toBeInTheDocument()
    const grid = await screen.findByRole('list', { name: 'Saved designs' })
    expect(within(grid).getByRole('heading', { name: '<img src=x onerror=alert(1)>' })).toBeInTheDocument()
    expect(within(grid).queryByText('Current sketch')).toBeNull()
    expect(container.querySelector('img[src="x"]')).toBeNull()
    expect(screen.getByRole('note')).toHaveTextContent('1 saved design cannot be shown')
    expect(mocks.listSavedDesigns).toHaveBeenCalledWith('u1', expect.anything())
  })

  it('handles empty, error and refresh states', async () => {
    mocks.listSavedDesigns
      .mockRejectedValueOnce(new Error('FashionRise is temporarily unavailable.'))
      .mockResolvedValueOnce({ designs: [], damaged: [] })
      .mockResolvedValueOnce({ designs: [RECORD], damaged: [] })
    renderAt('/studio/designs')
    expect(screen.getByRole('status', { name: '' })).toHaveTextContent('Loading your designs')
    expect(await screen.findByRole('alert')).toHaveTextContent('temporarily unavailable')
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText(/No saved designs yet/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Refresh' }))
    expect(await screen.findByRole('heading', { name: 'Evening gown' })).toBeInTheDocument()
    expect(mocks.listSavedDesigns).toHaveBeenCalledTimes(3)
  })
})

async function openFromLibrary() {
  fireEvent.click(await screen.findByRole('button', { name: 'Open Evening gown in Studio' }))
}

describe('Reopen a saved design', () => {
  it('replaces the working draft through an OCC write after confirmation', async () => {
    renderAt('/studio/designs')
    await ready()
    await openFromLibrary()
    const dialog = await screen.findByRole('dialog', { name: 'Open “Evening gown”?' })
    expect(mocks.persistStudioDraft).not.toHaveBeenCalled()
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Replace and open' }))
    })
    expect(mocks.persistStudioDraft).toHaveBeenCalledTimes(1)
    const call = mocks.persistStudioDraft.mock.calls[0]![0]
    expect(call).toMatchObject({
      designId: 'draft-1',
      expectedRevision: 3,
      skipLocalWrite: true,
      lastSyncedFingerprint: null,
    })
    expect(call.document).toMatchObject({
      schema: 'fashionrise.studio.draft.v1',
      clientRevision: 4,
      model: 'male',
      dimmed: true,
      brush: RECORD.snapshot.brush,
      strokes: RECORD.snapshot.strokes,
    })
    expect(await screen.findByRole('heading', { name: 'New Design' })).toBeInTheDocument()
    expect(strokeIds()).toBe('snap-1,snap-2')
    for (const undo of screen.getAllByRole('button', { name: 'Undo' })) expect(undo).toBeDisabled()
    expect(screen.getByRole('status', { name: /Opened “Evening gown” in Studio/ })).toBeInTheDocument()
    expect(screen.getByText('Saved')).toBeInTheDocument()
  })

  it('undo history never spans designs', async () => {
    renderAt('/studio')
    await ready()
    fireEvent.click(screen.getByRole('button', { name: 'Mock stroke' }))
    await screen.findByText('Saved on this device')
    fireEvent.click(screen.getByRole('button', { name: 'More' }))
    await act(async () => {
      fireEvent.click(screen.getByRole('menuitem', { name: 'Save now' }))
    })
    await screen.findByText('Saved')
    for (const undo of screen.getAllByRole('button', { name: 'Undo' })) expect(undo).toBeEnabled()
    fireEvent.click(within(screen.getByRole('navigation', { name: 'FashionRise' })).getByRole('button', { name: 'My Designs' }))
    await openFromLibrary()
    const dialog = await screen.findByRole('dialog', { name: 'Open “Evening gown”?' })
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Replace and open' }))
    })
    await screen.findByRole('heading', { name: 'New Design' })
    expect(strokeIds()).toBe('snap-1,snap-2')
    for (const undo of screen.getAllByRole('button', { name: 'Undo' })) expect(undo).toBeDisabled()
    const openCall = mocks.persistStudioDraft.mock.calls.find((c) => c[0].document.strokes[0]?.id === 'snap-1')
    expect(openCall![0].expectedRevision).toBe(4)
  })

  it('cancel leaves everything untouched', async () => {
    renderAt('/studio/designs')
    await ready()
    await openFromLibrary()
    const dialog = await screen.findByRole('dialog', { name: 'Open “Evening gown”?' })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(mocks.persistStudioDraft).not.toHaveBeenCalled()
  })

  it('opens directly into an empty working draft', async () => {
    cleanRestore(workingDoc({ strokes: [] }))
    renderAt('/studio/designs')
    await ready()
    await act(async () => {
      await openFromLibrary()
    })
    await screen.findByRole('heading', { name: 'New Design' })
    expect(strokeIds()).toBe('snap-1,snap-2')
    expect(mocks.persistStudioDraft.mock.calls[0]![0].createOnly).toBeFalsy()
  })

  it('first-time users create the working draft with createOnly', async () => {
    mocks.restoreStudioDraft.mockResolvedValue({
      designId: null,
      document: workingDoc({ strokes: [], clientRevision: 1 }),
      syncedRevision: null,
      conflict: null,
      notice: null,
    })
    renderAt('/studio/designs')
    await screen.findByRole('heading', { name: 'My Designs' })
    await act(async () => {
      await openFromLibrary()
    })
    await screen.findByRole('heading', { name: 'New Design' })
    expect(strokeIds()).toBe('snap-1,snap-2')
    expect(mocks.persistStudioDraft).toHaveBeenCalledWith(
      expect.objectContaining({
        designId: null,
        expectedRevision: null,
        createOnly: true,
        skipLocalWrite: true,
      }),
    )
  })

  it('refuses when another device creates a draft during an empty open', async () => {
    mocks.restoreStudioDraft.mockResolvedValue({
      designId: null,
      document: workingDoc({ strokes: [], clientRevision: 1 }),
      syncedRevision: null,
      conflict: null,
      notice: null,
    })
    const foreign = workingDoc({
      clientRevision: 2,
      strokes: [{ ...STROKE, id: 'other-device' }],
      model: 'blank',
    })
    mocks.persistStudioDraft.mockResolvedValueOnce({
      ok: false,
      conflict: { local: workingDoc({ strokes: [] }), server: foreign, designId: 'foreign-draft' },
      localPersisted: true,
      error: 'Your working draft was created on another device.',
    })
    renderAt('/studio/designs')
    await screen.findByRole('heading', { name: 'My Designs' })
    await act(async () => {
      await openFromLibrary()
    })
    expect(await screen.findByRole('dialog', { name: 'Draft recovery conflict' })).toBeInTheDocument()
    expect(strokeIds()).toBe('')
    expect(mocks.persistStudioDraft.mock.calls[0]![0].createOnly).toBe(true)
    expect(
      screen.getByRole('status', { name: /changed on another device, so the design was not opened/ }),
    ).toBeInTheDocument()
  })

  it('retries createOnly open after a committed create whose response and reconcile list were lost', async () => {
    mocks.restoreStudioDraft.mockResolvedValue({
      designId: null,
      document: workingDoc({ strokes: [], clientRevision: 1 }),
      syncedRevision: null,
      conflict: null,
      notice: null,
    })
    // A list after the first attempt would see the draft we just created — createOnly must
    // still recover it. There is no blocking list preflight anymore.
    mocks.listMyDesigns.mockResolvedValue([
      {
        id: 'draft-recovered',
        user_id: 'u1',
        title: 'Studio working draft',
        description: null,
        garment_category: 'studio',
        design_data: {
          schema: 'fashionrise.studio.draft.v1',
          strokes: RECORD.snapshot.strokes,
          model: RECORD.snapshot.model,
          customReferenceUrl: null,
          customReferenceKey: null,
          brush: RECORD.snapshot.brush,
          dimmed: RECORD.snapshot.dimmed,
          clientRevision: 2,
          updatedAt: '2026-10-20T10:00:00.000Z',
        },
        metadata: { draftKind: 'studio_working_draft', clientRevision: 2 },
        visibility: 'private',
        status: 'draft',
        created_at: '2026-10-20T10:00:00.000Z',
        updated_at: '2026-10-20T10:00:00.000Z',
      },
    ])
    mocks.persistStudioDraft.mockResolvedValueOnce({
      ok: false,
      conflict: null,
      localPersisted: false,
      error: 'Unable to reach FashionRise.',
      designId: null,
    })

    renderAt('/studio/designs')
    await screen.findByRole('heading', { name: 'My Designs' })
    await act(async () => {
      await openFromLibrary()
    })
    const err = await screen.findByRole('dialog', { name: 'Could not open design' })
    expect(within(err).getByRole('alert')).toHaveTextContent(/could not be confirmed/i)
    expect(within(err).getByRole('button', { name: 'Try again' })).toBeInTheDocument()
    expect(mocks.persistStudioDraft).toHaveBeenCalledTimes(1)
    expect(mocks.persistStudioDraft.mock.calls[0]![0].createOnly).toBe(true)

    mocks.persistStudioDraft.mockImplementationOnce(({ document }: { document: StudioDraftDocument }) =>
      Promise.resolve({
        ok: true as const,
        designId: 'draft-recovered',
        document,
        fingerprint: draftContentFingerprint({
          ...document,
          customReferenceUrl: null,
          customReferenceKey: null,
        }),
        syncedRevision: document.clientRevision,
        localPersisted: true,
      }),
    )
    await act(async () => {
      fireEvent.click(within(err).getByRole('button', { name: 'Try again' }))
    })
    await screen.findByRole('heading', { name: 'New Design' })
    expect(strokeIds()).toBe('snap-1,snap-2')
    expect(mocks.persistStudioDraft).toHaveBeenCalledTimes(2)
    expect(mocks.persistStudioDraft.mock.calls[1]![0]).toMatchObject({
      designId: null,
      createOnly: true,
      expectedRevision: null,
    })
    expect(screen.queryByRole('dialog', { name: 'Could not open design' })).toBeNull()
    expect(screen.queryByText(/Reload Studio/i)).toBeNull()
  })

  it('refuses while edits are unsynced, then waits for the queued save before switching', async () => {
    renderAt('/studio')
    await ready()
    fireEvent.click(screen.getByRole('button', { name: 'Mock stroke' }))
    await screen.findByText('Saved on this device')
    fireEvent.click(within(screen.getByRole('navigation', { name: 'FashionRise' })).getByRole('button', { name: 'My Designs' }))
    await openFromLibrary()
    const blocked = await screen.findByRole('dialog', { name: 'Your Studio sketch is not saved yet' })
    expect(mocks.persistStudioDraft).not.toHaveBeenCalled()

    let finishAutosave!: () => void
    mocks.persistStudioDraft.mockImplementationOnce(
      (args: { document: StudioDraftDocument; designId: string | null }) =>
        new Promise((resolve) => {
          finishAutosave = () => resolve(okPersist(args))
        }),
    )
    fireEvent.click(within(blocked).getByRole('button', { name: 'Retry save' }))
    await waitFor(() => expect(mocks.persistStudioDraft).toHaveBeenCalledTimes(1))
    const autosave = mocks.persistStudioDraft.mock.calls[0]![0]
    expect(autosave.expectedRevision).toBe(3)
    expect(autosave.lastSyncedFingerprint).not.toBeNull()
    expect(autosave.document.strokes.map((s: Stroke) => s.id)).toEqual(['restored-1', 'new-1'])
    expect(screen.queryByRole('dialog', { name: /Open “/ })).toBeNull()

    await act(async () => finishAutosave())
    const confirm = await screen.findByRole('dialog', { name: 'Open “Evening gown”?' })
    await act(async () => {
      fireEvent.click(within(confirm).getByRole('button', { name: 'Replace and open' }))
    })
    const open = mocks.persistStudioDraft.mock.calls[1]![0]
    expect(open.expectedRevision).toBe(autosave.document.clientRevision)
    expect(open.document.clientRevision).toBe(autosave.document.clientRevision + 1)
    await screen.findByRole('heading', { name: 'New Design' })
    expect(strokeIds()).toBe('snap-1,snap-2')
  })

  it('aborts on another device’s change and shows the existing conflict choice', async () => {
    const other = workingDoc({ clientRevision: 5, strokes: [{ ...STROKE, id: 'other-device' }] })
    mocks.persistStudioDraft.mockResolvedValueOnce({
      ok: false,
      conflict: { local: workingDoc(), server: other, designId: 'draft-1' },
      localPersisted: true,
      error: 'Draft was updated elsewhere.',
    })
    renderAt('/studio/designs')
    await ready()
    await openFromLibrary()
    const dialog = await screen.findByRole('dialog', { name: 'Open “Evening gown”?' })
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Replace and open' }))
    })
    expect(await screen.findByRole('dialog', { name: 'Draft recovery conflict' })).toBeInTheDocument()
    expect(strokeIds()).toBe('restored-1')
    expect(screen.getByRole('status', { name: /changed on another device, so the design was not opened/ })).toBeInTheDocument()
  })

  it('treats a 409 carrying our own content as a recovered lost response', async () => {
    mocks.persistStudioDraft.mockImplementationOnce(({ document }: { document: StudioDraftDocument }) =>
      Promise.resolve({
        ok: false,
        conflict: { local: document, server: { ...document }, designId: 'draft-1' },
        localPersisted: false,
        error: 'Draft was updated elsewhere.',
      }),
    )
    renderAt('/studio/designs')
    await ready()
    await openFromLibrary()
    const dialog = await screen.findByRole('dialog', { name: 'Open “Evening gown”?' })
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Replace and open' }))
    })
    await screen.findByRole('heading', { name: 'New Design' })
    expect(strokeIds()).toBe('snap-1,snap-2')
    expect(mocks.persistLocalRecovery).toHaveBeenCalledWith(
      expect.objectContaining({ designId: 'draft-1', syncedRevision: 4 }),
    )
    expect(screen.queryByRole('dialog', { name: 'Draft recovery conflict' })).toBeNull()
  })

  it('an uncertain write never claims the server was unchanged and can be retried', async () => {
    mocks.persistStudioDraft.mockResolvedValueOnce({
      ok: false,
      conflict: null,
      localPersisted: false,
      error: 'Unable to reach FashionRise.',
      designId: 'draft-1',
    })
    renderAt('/studio/designs')
    await ready()
    await openFromLibrary()
    let dialog = await screen.findByRole('dialog', { name: 'Open “Evening gown”?' })
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Replace and open' }))
    })
    dialog = await screen.findByRole('dialog', { name: 'Could not open design' })
    const alert = within(dialog).getByRole('alert')
    expect(alert).toHaveTextContent(/could not be confirmed/i)
    expect(alert).not.toHaveTextContent(/Nothing was replaced/)
    // Still on My Designs — Studio view was not updated.
    expect(screen.getByRole('heading', { name: 'My Designs' })).toBeInTheDocument()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Try again' }))
    dialog = await screen.findByRole('dialog', { name: 'Open “Evening gown”?' })
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Replace and open' }))
    })
    await screen.findByRole('heading', { name: 'New Design' })
    expect(mocks.persistStudioDraft.mock.calls.map((c) => c[0].expectedRevision)).toEqual([3, 3])
    expect(strokeIds()).toBe('snap-1,snap-2')
  })

  it('recovers a lost response after the server write committed without overwriting', async () => {
    // First attempt: network drops after the server accepted our open write.
    mocks.persistStudioDraft.mockResolvedValueOnce({
      ok: false,
      conflict: null,
      localPersisted: false,
      error: 'Unable to reach FashionRise.',
      designId: 'draft-1',
    })
    renderAt('/studio/designs')
    await ready()
    await openFromLibrary()
    let dialog = await screen.findByRole('dialog', { name: 'Open “Evening gown”?' })
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Replace and open' }))
    })
    dialog = await screen.findByRole('dialog', { name: 'Could not open design' })
    expect(within(dialog).getByRole('alert')).toHaveTextContent(/could not be confirmed/i)
    expect(screen.getByRole('heading', { name: 'My Designs' })).toBeInTheDocument()

    // Retry: server already holds our opened content → recovered via conflict fingerprint match.
    mocks.persistStudioDraft.mockImplementationOnce(({ document }: { document: StudioDraftDocument }) =>
      Promise.resolve({
        ok: false,
        conflict: { local: document, server: { ...document }, designId: 'draft-1' },
        localPersisted: false,
        error: 'Draft was updated elsewhere.',
      }),
    )
    fireEvent.click(within(dialog).getByRole('button', { name: 'Try again' }))
    dialog = await screen.findByRole('dialog', { name: 'Open “Evening gown”?' })
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Replace and open' }))
    })
    await screen.findByRole('heading', { name: 'New Design' })
    expect(strokeIds()).toBe('snap-1,snap-2')
    expect(screen.queryByRole('dialog', { name: 'Draft recovery conflict' })).toBeNull()
    expect(mocks.persistLocalRecovery).toHaveBeenCalledWith(
      expect.objectContaining({ designId: 'draft-1', syncedRevision: 4 }),
    )
  })

  it('refuses a malformed or foreign design without retry', async () => {
    mocks.fetchSavedDesign.mockResolvedValueOnce({
      ok: false,
      error: 'This design cannot be opened because its saved data is not in a supported format.',
      reason: 'invalid',
    })
    renderAt('/studio/designs')
    await ready()
    await act(async () => {
      await openFromLibrary()
    })
    const dialog = await screen.findByRole('dialog', { name: 'Could not open design' })
    expect(within(dialog).queryByRole('button', { name: 'Try again' })).toBeNull()
    expect(mocks.persistStudioDraft).not.toHaveBeenCalled()
  })

  it('asks for the draft conflict to be resolved first', async () => {
    mocks.restoreStudioDraft.mockResolvedValue({
      designId: 'draft-1',
      document: workingDoc(),
      syncedRevision: 3,
      conflict: { local: workingDoc(), server: workingDoc({ clientRevision: 4, strokes: [] }), designId: 'draft-1' },
      notice: null,
    })
    renderAt('/studio/designs')
    await screen.findByText('Saved on this device')
    await act(async () => {
      await openFromLibrary()
    })
    const dialog = await screen.findByRole('dialog', { name: 'Resolve your draft first' })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Go to Studio' }))
    expect(await screen.findByRole('dialog', { name: 'Draft recovery conflict' })).toBeInTheDocument()
    expect(mocks.persistStudioDraft).not.toHaveBeenCalled()
  })
})
