import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  bumpDraftDocument,
  createEmptyDraftDocument,
  draftContentFingerprint,
} from '@/lib/draftDocument'
import {
  commitKeepDeviceChoice,
  commitUseCloudChoice,
  persistStudioDraft,
  restoreStudioDraft,
} from '@/lib/draftPersistence'
import type { StudioDraftDocument } from '@/lib/draftDocument'
import { StudioPage } from '@/pages/StudioPage'
import { ApiError } from '@/services/api/client'

const localStore = vi.hoisted(() => ({
  records: new Map<string, { userId: string; designId: string | null; document: StudioDraftDocument; savedAt: string; syncedRevision: number | null }>(),
  designIds: new Map<string, string>(),
  failReplace: false,
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
  DrawingCanvas: () => <div data-testid="drawing-canvas" />,
}))

vi.mock('@/lib/localDraftStore', () => ({
  readLocalDraft: async (userId: string) => localStore.records.get(userId) ?? null,
  writeLocalDraft: async (record: {
    userId: string
    designId: string | null
    document: StudioDraftDocument
    savedAt: string
    syncedRevision: number | null
  }) => {
    const existing = localStore.records.get(record.userId)
    if (existing && existing.document.clientRevision > record.document.clientRevision) {
      return { ok: true, wrote: false, reason: 'stale' }
    }
    localStore.records.set(record.userId, record)
    return { ok: true, wrote: true }
  },
  replaceLocalDraft: async (record: {
    userId: string
    designId: string | null
    document: StudioDraftDocument
    savedAt: string
    syncedRevision: number | null
  }) => {
    if (localStore.failReplace) return { ok: false, error: 'IndexedDB write failed' }
    localStore.records.set(record.userId, record)
    return { ok: true, wrote: true }
  },
  readStoredDesignId: (userId: string) => localStore.designIds.get(userId) ?? null,
  writeStoredDesignId: (userId: string, designId: string) => {
    localStore.designIds.set(userId, designId)
  },
  clearLocalDraft: async (userId: string) => {
    localStore.records.delete(userId)
  },
}))

const api = vi.hoisted(() => ({
  designs: new Map<string, { id: string; design_data: StudioDraftDocument; metadata: Record<string, unknown>; visibility: string; updated_at: string }>(),
  updateCalls: 0,
  raceOnExpected: null as number | null,
  createReturnsDifferent: false,
}))

function designRow(id: string, doc: StudioDraftDocument) {
  return {
    id,
    user_id: 'u1',
    title: 'Studio working draft',
    description: null,
    garment_category: 'studio',
    design_data: doc as unknown as Record<string, unknown>,
    metadata: { draftKind: 'studio_working_draft', clientRevision: doc.clientRevision },
    visibility: 'private',
    status: 'draft',
    created_at: '2026-10-19T00:00:00.000Z',
    updated_at: '2026-10-19T00:00:00.000Z',
  }
}

vi.mock('@/services/designsApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/designsApi')>()
  return {
    ...actual,
    listMyDesigns: async () =>
      [...api.designs.values()].map((d) => designRow(d.id, d.design_data)),
    getDesign: async (id: string) => {
      const d = api.designs.get(id)
      if (!d) throw new ApiError('missing', 404, null)
      return designRow(d.id, d.design_data)
    },
    createStudioDraft: async (document: StudioDraftDocument) => {
      if (api.createReturnsDifferent) {
        const other = bumpDraftDocument(createEmptyDraftDocument(), { model: 'blank' })
        return designRow('created-other', other)
      }
      const cloud = actual.documentForCloud(document)
      api.designs.set('created-1', {
        id: 'created-1',
        design_data: cloud,
        metadata: { draftKind: 'studio_working_draft' },
        visibility: 'private',
        updated_at: new Date().toISOString(),
      })
      return designRow('created-1', cloud)
    },
    updateStudioDraft: async (
      designId: string,
      document: StudioDraftDocument,
      options?: { expectedRevision?: number | null },
    ) => {
      api.updateCalls += 1
      const existing = api.designs.get(designId)
      if (!existing) throw new ApiError('missing', 404, null)
      if (api.raceOnExpected != null && options?.expectedRevision === api.raceOnExpected) {
        const raced = bumpDraftDocument(existing.design_data, { model: 'male' })
        raced.clientRevision = api.raceOnExpected + 2
        existing.design_data = raced
        throw new ApiError('conflict', 409, {
          detail: {
            code: 'conflict',
            message: 'Draft was updated elsewhere.',
            payload: {
              expected_revision: options.expectedRevision,
              current_revision: raced.clientRevision,
              design: designRow(designId, raced),
            },
          },
        })
      }
      if (
        options?.expectedRevision != null &&
        existing.design_data.clientRevision !== options.expectedRevision
      ) {
        throw new ApiError('conflict', 409, {
          detail: {
            code: 'conflict',
            message: 'Draft was updated elsewhere.',
            payload: {
              expected_revision: options.expectedRevision,
              current_revision: existing.design_data.clientRevision,
              design: designRow(designId, existing.design_data),
            },
          },
        })
      }
      const cloud = actual.documentForCloud(document)
      if (cloud.clientRevision <= existing.design_data.clientRevision &&
        draftContentFingerprint(cloud) !== draftContentFingerprint(existing.design_data)) {
        throw new ApiError('conflict', 409, {
          detail: {
            code: 'conflict',
            message: 'Studio draft revision must advance when content changes.',
            payload: {
              expected_revision: options?.expectedRevision,
              current_revision: existing.design_data.clientRevision,
              design: designRow(designId, existing.design_data),
            },
          },
        })
      }
      existing.design_data = cloud
      return designRow(designId, cloud)
    },
  }
})

function strokeDoc(model: StudioDraftDocument['model'], revision: number): StudioDraftDocument {
  const base = createEmptyDraftDocument()
  const next = bumpDraftDocument(base, {
    model,
    strokes: [
      {
        id: `stroke-${model}`,
        tool: 'draw',
        points: [1, 2, 1],
        color: '#112233',
        size: 4,
        opacity: 0.8,
      },
    ],
    brush: { sizeId: 'bold', opacity: 0.4, color: '#ABCDEF' },
  })
  next.clientRevision = revision
  return next
}

function seedConflict(local: StudioDraftDocument, server: StudioDraftDocument) {
  localStore.records.set('u1', {
    userId: 'u1',
    designId: 'd1',
    document: local,
    savedAt: '2026-10-19T01:00:00.000Z',
    syncedRevision: 1,
  })
  localStore.designIds.set('u1', 'd1')
  api.designs.set('d1', {
    id: 'd1',
    design_data: server,
    metadata: { draftKind: 'studio_working_draft' },
    visibility: 'private',
    updated_at: '2026-10-19T02:00:00.000Z',
  })
}

describe('WEB-V2.1C conflict resolution', () => {
  beforeEach(() => {
    localStore.records.clear()
    localStore.designIds.clear()
    localStore.failReplace = false
    api.designs.clear()
    api.updateCalls = 0
    api.raceOnExpected = null
    api.createReturnsDifferent = false
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: () => ({
        matches: false,
        media: '',
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }),
    })
  })

  it('does not cloud-save while a conflict dialog is open', async () => {
    seedConflict(strokeDoc('male', 8), strokeDoc('blank', 3))
    render(
      <MemoryRouter>
        <StudioPage />
      </MemoryRouter>,
    )
    expect(await screen.findByRole('dialog', { name: /draft recovery conflict/i })).toBeInTheDocument()
    expect(api.updateCalls).toBe(0)
    expect(screen.queryByText(/^Saved$/)).not.toBeInTheDocument()
  })

  it('Keep this device rebases above the server revision and survives refresh', async () => {
    const local = strokeDoc('male', 2)
    const server = strokeDoc('blank', 7)
    seedConflict(local, server)
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <StudioPage />
      </MemoryRouter>,
    )
    await user.click(await screen.findByRole('button', { name: 'Keep this device' }))
    expect(await screen.findByText('Saved')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    const stored = api.designs.get('d1')!.design_data
    expect(stored.clientRevision).toBeGreaterThan(7)
    expect(stored.strokes[0]?.id).toBe('stroke-male')
    expect(stored.brush.sizeId).toBe('bold')

    const refreshed = await restoreStudioDraft('u1')
    expect(refreshed.conflict).toBeNull()
    expect(refreshed.document.strokes[0]?.id).toBe('stroke-male')
    expect(refreshed.document.model).toBe('male')
  })

  it('Keep this device also wins when the local revision is already higher', async () => {
    seedConflict(strokeDoc('male', 9), strokeDoc('blank', 3))
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <StudioPage />
      </MemoryRouter>,
    )
    await user.click(await screen.findByRole('button', { name: 'Keep this device' }))
    expect(await screen.findByText('Saved')).toBeInTheDocument()
    expect(api.designs.get('d1')!.design_data.clientRevision).toBeGreaterThan(9)
    expect(api.designs.get('d1')!.design_data.model).toBe('male')
  })

  it('renews the conflict when the server advances during Keep this device', async () => {
    seedConflict(strokeDoc('female', 2), strokeDoc('blank', 4))
    api.raceOnExpected = 4
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <StudioPage />
      </MemoryRouter>,
    )
    await user.click(await screen.findByRole('button', { name: 'Keep this device' }))
    expect(await screen.findByRole('dialog', { name: /draft recovery conflict/i })).toBeInTheDocument()
    expect(screen.queryByText(/^Saved$/)).not.toBeInTheDocument()
    expect(api.designs.get('d1')!.design_data.model).toBe('male')
  })

  it('Use cloud draft replaces a higher local revision and refresh does not reopen the dialog', async () => {
    seedConflict(strokeDoc('male', 9), strokeDoc('blank', 2))
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <StudioPage />
      </MemoryRouter>,
    )
    expect(screen.queryByText(/^Saved$/)).not.toBeInTheDocument()
    await user.click(await screen.findByRole('button', { name: 'Use cloud draft' }))
    expect(await screen.findByText('Saved')).toBeInTheDocument()
    expect(localStore.records.get('u1')!.document.clientRevision).toBe(2)
    expect(localStore.records.get('u1')!.document.model).toBe('blank')

    const refreshed = await restoreStudioDraft('u1')
    expect(refreshed.conflict).toBeNull()
    expect(refreshed.document.model).toBe('blank')
    expect(refreshed.document.strokes[0]?.id).toBe('stroke-blank')
  })

  it('does not show Saved when the Use cloud IndexedDB replacement fails', async () => {
    seedConflict(strokeDoc('male', 9), strokeDoc('blank', 2))
    localStore.failReplace = true
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <StudioPage />
      </MemoryRouter>,
    )
    await user.click(await screen.findByRole('button', { name: 'Use cloud draft' }))
    expect(await screen.findByText('Save failed')).toBeInTheDocument()
    expect(screen.queryByText(/^Saved$/)).not.toBeInTheDocument()
    expect(screen.getByRole('dialog', { name: /draft recovery conflict/i })).toBeInTheDocument()
    expect(localStore.records.get('u1')!.document.model).toBe('male')
  })

  it('does not report success when create/reconcile acknowledges different content', async () => {
    api.createReturnsDifferent = true
    const local = strokeDoc('male', 4)
    const created = await persistStudioDraft({
      userId: 'u1',
      designId: null,
      document: local,
      fingerprint: draftContentFingerprint(local),
      lastSyncedFingerprint: null,
      expectedRevision: null,
    })
    expect(created.ok).toBe(false)
    if (!created.ok) {
      expect(created.conflict?.server.model).toBe('blank')
      expect(created.conflict?.local.strokes[0]?.id).toBe('stroke-male')
    }
  })

  it('commit helpers preserve strokes and surface a failed cloud replacement', async () => {
    const local = strokeDoc('male', 2)
    const server = strokeDoc('blank', 5)
    api.designs.set('d1', {
      id: 'd1',
      design_data: server,
      metadata: {},
      visibility: 'private',
      updated_at: new Date().toISOString(),
    })
    const kept = await commitKeepDeviceChoice({
      userId: 'u1',
      designId: 'd1',
      local,
      serverRevision: server.clientRevision,
    })
    expect(kept.ok).toBe(true)
    if (kept.ok) {
      expect(kept.document.strokes[0]?.id).toBe('stroke-male')
      expect(kept.syncedRevision).toBeGreaterThan(server.clientRevision)
    }

    localStore.failReplace = true
    const cloud = await commitUseCloudChoice({
      userId: 'u1',
      designId: 'd1',
      server,
    })
    expect(cloud.ok).toBe(false)
  })
})
