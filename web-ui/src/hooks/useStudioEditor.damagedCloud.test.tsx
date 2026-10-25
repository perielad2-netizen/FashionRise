import { act, renderHook, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  bumpDraftDocument,
  createEmptyDraftDocument,
  draftContentFingerprint,
  type StudioDraftDocument,
} from '@/lib/draftDocument'
import { useStudioEditor } from '@/hooks/useStudioEditor'

const localStore = vi.hoisted(() => ({
  records: new Map<string, unknown>(),
  designIds: new Map<string, string>(),
}))

const api = vi.hoisted(() => ({
  designs: new Map<
    string,
    {
      id: string
      design_data: Record<string, unknown>
      metadata: Record<string, unknown>
      visibility: string
      updated_at: string
    }
  >(),
  createCalls: 0,
  updateCalls: [] as Array<{ id: string; expected?: number | null }>,
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
    localStore.records.set(record.userId, record)
    return { ok: true }
  },
  readStoredDesignId: (userId: string) => localStore.designIds.get(userId) ?? null,
  writeStoredDesignId: (userId: string, designId: string) => {
    localStore.designIds.set(userId, designId)
  },
  clearLocalDraft: async (userId: string) => {
    localStore.records.delete(userId)
  },
}))

vi.mock('@/services/designsApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/designsApi')>()
  return {
    ...actual,
    listMyDesigns: async () =>
      [...api.designs.values()].map((d) => ({
        id: d.id,
        user_id: 'u1',
        title: 'Studio working draft',
        description: null,
        garment_category: 'studio',
        design_data: d.design_data,
        metadata: d.metadata,
        visibility: d.visibility,
        status: 'draft',
        created_at: d.updated_at,
        updated_at: d.updated_at,
      })),
    getDesign: async (id: string) => {
      const d = api.designs.get(id)
      if (!d) {
        const { ApiError } = await import('@/services/api/client')
        throw new ApiError('not found', 404, null)
      }
      return {
        id: d.id,
        user_id: 'u1',
        title: 'Studio working draft',
        description: null,
        garment_category: 'studio',
        design_data: d.design_data,
        metadata: d.metadata,
        visibility: d.visibility,
        status: 'draft',
        created_at: d.updated_at,
        updated_at: d.updated_at,
      }
    },
    createStudioDraft: async () => {
      api.createCalls += 1
      throw new Error('createStudioDraft must not run during damaged-cloud boot')
    },
    updateStudioDraft: async (
      designId: string,
      _document: StudioDraftDocument,
      options?: { expectedRevision?: number | null },
    ) => {
      api.updateCalls.push({ id: designId, expected: options?.expectedRevision })
      throw new Error('updateStudioDraft must not run during damaged-cloud boot')
    },
  }
})

vi.mock('@/services/auth/AuthProvider', () => ({
  useAuth: () => ({
    user: { id: 'u1', username: 'demo' },
    logout: vi.fn(),
    isAuthenticated: true,
    bootstrapping: false,
  }),
}))

function wrapper({ children }: { children: ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>
}

function malformedV2(): Record<string, unknown> {
  return {
    schema: 'fashionrise.studio.draft.v2',
    strokes: [
      {
        id: 'f1',
        tool: 'draw',
        points: [1, 2, 0.5],
        color: '#1C1C1E',
        size: 2,
        opacity: 1,
      },
    ],
    fills: [],
    activeSide: 'front',
    back: { strokes: 'broken', fills: [] },
    model: 'female-straight',
    customReferenceUrl: null,
    customReferenceKey: null,
    brush: { sizeId: 'thin', opacity: 1, color: '#1C1C1E' },
    dimmed: false,
    clientRevision: 6,
    updatedAt: '2026-10-25T00:00:00.000Z',
  }
}

describe('useStudioEditor damaged cloud boot', () => {
  beforeEach(() => {
    localStore.records.clear()
    localStore.designIds.clear()
    api.designs.clear()
    api.createCalls = 0
    api.updateCalls = []
  })

  it('does not auto PUT/POST when cloud V2 is damaged and a stale local copy exists', async () => {
    const raw = malformedV2()
    api.designs.set('cloud-bad', {
      id: 'cloud-bad',
      design_data: raw,
      metadata: {
        draftKind: 'studio_working_draft',
        clientRevision: 6,
        schema: 'fashionrise.studio.draft.v2',
      },
      visibility: 'private',
      updated_at: '2026-10-25T00:00:00.000Z',
    })
    localStore.designIds.set('u1', 'cloud-bad')
    const local = bumpDraftDocument(createEmptyDraftDocument(), {
      strokes: [
        {
          id: 'local-1',
          tool: 'draw',
          points: [9, 9, 0.5],
          color: '#111111',
          size: 2,
          opacity: 1,
        },
      ],
      model: 'male',
    })
    localStore.records.set('u1', {
      userId: 'u1',
      designId: 'cloud-bad',
      document: local,
      savedAt: '2026-10-24T00:00:00.000Z',
      syncedRevision: 2,
    })

    const { result } = renderHook(() => useStudioEditor(), { wrapper })
    await waitFor(() => expect(result.current.ready).toBe(true))

    expect(result.current.damagedCloud?.designId).toBe('cloud-bad')
    expect(result.current.studioNotice).toMatch(/could not be read/i)
    expect(result.current.strokes.map((s) => s.id)).toEqual(['local-1'])
    expect(api.createCalls).toBe(0)
    expect(api.updateCalls).toHaveLength(0)
    expect(api.designs.get('cloud-bad')!.design_data).toEqual(raw)

    await act(async () => {
      result.current.retrySave()
    })
    await act(async () => {
      await Promise.resolve()
    })
    expect(api.createCalls).toBe(0)
    expect(api.updateCalls).toHaveLength(0)
    expect(draftContentFingerprint(local)).toBe(
      draftContentFingerprint(
        (localStore.records.get('u1') as { document: StudioDraftDocument }).document,
      ),
    )
  })

  it('does not auto create a cloud draft when damaged V2 exists with no local copy', async () => {
    api.designs.set('cloud-bad', {
      id: 'cloud-bad',
      design_data: malformedV2(),
      metadata: { draftKind: 'studio_working_draft', clientRevision: 6 },
      visibility: 'private',
      updated_at: '2026-10-25T00:00:00.000Z',
    })
    localStore.designIds.set('u1', 'cloud-bad')

    const { result } = renderHook(() => useStudioEditor(), { wrapper })
    await waitFor(() => expect(result.current.ready).toBe(true))
    expect(result.current.damagedCloud?.designId).toBe('cloud-bad')
    expect(result.current.damagedCloudDialogOpen).toBe(true)
    expect(api.createCalls).toBe(0)
    expect(api.updateCalls).toHaveLength(0)
  })
})
