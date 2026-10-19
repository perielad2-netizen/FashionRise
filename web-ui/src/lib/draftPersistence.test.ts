import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  bumpDraftDocument,
  createEmptyDraftDocument,
  draftContentFingerprint,
} from '@/lib/draftDocument'
import { persistStudioDraft, restoreStudioDraft } from '@/lib/draftPersistence'
import type { StudioDraftDocument } from '@/lib/draftDocument'

const localStore = vi.hoisted(() => ({
  records: new Map<string, unknown>(),
  designIds: new Map<string, string>(),
  failWrites: false,
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
    if (localStore.failWrites) return { ok: false, error: 'IndexedDB write failed' }
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

const api = vi.hoisted(() => ({
  designs: new Map<string, { id: string; design_data: StudioDraftDocument; metadata: Record<string, unknown>; visibility: string; updated_at: string }>(),
  failCreateOnce: false,
  createCalls: 0,
  updateCalls: [] as Array<{ id: string; expected?: number | null }>,
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
        design_data: d.design_data as unknown as Record<string, unknown>,
        metadata: d.metadata,
        visibility: d.visibility,
        status: 'draft',
        created_at: d.updated_at,
        updated_at: d.updated_at,
      })),
    getDesign: async (id: string) => {
      const d = api.designs.get(id)
      if (!d) throw new Error('missing')
      return {
        id: d.id,
        user_id: 'u1',
        title: 'Studio working draft',
        description: null,
        garment_category: 'studio',
        design_data: d.design_data as unknown as Record<string, unknown>,
        metadata: d.metadata,
        visibility: d.visibility,
        status: 'draft',
        created_at: d.updated_at,
        updated_at: d.updated_at,
      }
    },
    createStudioDraft: async (document: StudioDraftDocument) => {
      api.createCalls += 1
      if (api.failCreateOnce) {
        api.failCreateOnce = false
        // Simulate lost response: server already has the draft.
        const id = 'design-recovered'
        api.designs.set(id, {
          id,
          design_data: actual.documentForCloud(document),
          metadata: { draftKind: 'studio_working_draft', clientRevision: document.clientRevision },
          visibility: 'private',
          updated_at: new Date().toISOString(),
        })
        throw new Error('network dropped after create')
      }
      const id = `design-${api.createCalls}`
      const cloud = actual.documentForCloud(document)
      api.designs.set(id, {
        id,
        design_data: cloud,
        metadata: { draftKind: 'studio_working_draft', clientRevision: cloud.clientRevision },
        visibility: 'private',
        updated_at: new Date().toISOString(),
      })
      return {
        id,
        user_id: 'u1',
        title: 'Studio working draft',
        description: null,
        garment_category: 'studio',
        design_data: cloud as unknown as Record<string, unknown>,
        metadata: { draftKind: 'studio_working_draft', clientRevision: cloud.clientRevision },
        visibility: 'private',
        status: 'draft',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }
    },
    updateStudioDraft: async (
      designId: string,
      document: StudioDraftDocument,
      options?: { expectedRevision?: number | null },
    ) => {
      api.updateCalls.push({ id: designId, expected: options?.expectedRevision })
      const existing = api.designs.get(designId)
      if (!existing) throw new Error('missing')
      if (
        options?.expectedRevision != null &&
        existing.design_data.clientRevision !== options.expectedRevision
      ) {
        const { ApiError } = await import('@/services/api/client')
        throw new ApiError('conflict', 409, {
          detail: {
            code: 'conflict',
            message: 'Draft was updated elsewhere.',
            payload: {
              expected_revision: options.expectedRevision,
              current_revision: existing.design_data.clientRevision,
              design: {
                id: designId,
                user_id: 'u1',
                title: 'Studio working draft',
                description: null,
                garment_category: 'studio',
                design_data: existing.design_data,
                metadata: existing.metadata,
                visibility: 'private',
                status: 'draft',
                created_at: existing.updated_at,
                updated_at: existing.updated_at,
              },
            },
          },
        })
      }
      const cloud = actual.documentForCloud(document)
      existing.design_data = cloud
      existing.metadata = { draftKind: 'studio_working_draft', clientRevision: cloud.clientRevision }
      existing.updated_at = new Date().toISOString()
      return {
        id: designId,
        user_id: 'u1',
        title: 'Studio working draft',
        description: null,
        garment_category: 'studio',
        design_data: cloud as unknown as Record<string, unknown>,
        metadata: existing.metadata,
        visibility: 'private',
        status: 'draft',
        created_at: existing.updated_at,
        updated_at: existing.updated_at,
      }
    },
  }
})

function strokedDoc(): StudioDraftDocument {
  const base = createEmptyDraftDocument()
  return bumpDraftDocument(base, {
    strokes: [
      {
        id: 'stroke-1',
        tool: 'draw',
        points: [10, 20, 0.8, 30, 40, 0.9],
        color: '#1C1C1E',
        size: 2,
        opacity: 1,
      },
    ],
    model: 'male',
    brush: { sizeId: 'bold', opacity: 0.7, color: '#AABBCC' },
  })
}

describe('draftPersistence WEB-V2.1A', () => {
  beforeEach(() => {
    localStore.records.clear()
    localStore.designIds.clear()
    localStore.failWrites = false
    api.designs.clear()
    api.failCreateOnce = false
    api.createCalls = 0
    api.updateCalls = []
  })

  it('restores a nonempty local document while the empty editor would otherwise win', async () => {
    const local = strokedDoc()
    localStore.records.set('u1', {
      userId: 'u1',
      designId: null,
      document: local,
      savedAt: new Date().toISOString(),
      syncedRevision: null,
    })

    const restored = await restoreStudioDraft('u1')
    expect(restored.document.strokes).toHaveLength(1)
    expect(restored.document.model).toBe('male')
    expect(restored.document.brush.sizeId).toBe('bold')
    expect(restored.conflict).toBeNull()
  })

  it('requires explicit choice when local and server content differ', async () => {
    const local = strokedDoc()
    const server = bumpDraftDocument(createEmptyDraftDocument(), { model: 'blank' })
    localStore.records.set('u1', {
      userId: 'u1',
      designId: 'd1',
      document: local,
      savedAt: new Date().toISOString(),
      syncedRevision: 1,
    })
    localStore.designIds.set('u1', 'd1')
    api.designs.set('d1', {
      id: 'd1',
      design_data: server,
      metadata: { draftKind: 'studio_working_draft', clientRevision: server.clientRevision },
      visibility: 'private',
      updated_at: new Date().toISOString(),
    })

    const restored = await restoreStudioDraft('u1')
    expect(restored.conflict).not.toBeNull()
    expect(restored.conflict?.local.strokes).toHaveLength(1)
    expect(restored.conflict?.server.model).toBe('blank')
  })

  it('surfaces IndexedDB write failures instead of claiming device save', async () => {
    localStore.failWrites = true
    const doc = strokedDoc()
    const result = await persistStudioDraft({
      userId: 'u1',
      designId: null,
      document: doc,
      fingerprint: draftContentFingerprint(doc),
      lastSyncedFingerprint: null,
      expectedRevision: null,
    })
    expect(localStore.records.size).toBe(0)
    // Cloud create can still succeed, but localPersisted must stay false when IDB rejects.
    expect(result.localPersisted).toBe(false)
  })

  it('rejects stale expected_revision with a conflict payload', async () => {
    const server = strokedDoc()
    api.designs.set('d1', {
      id: 'd1',
      design_data: server,
      metadata: { draftKind: 'studio_working_draft', clientRevision: server.clientRevision },
      visibility: 'private',
      updated_at: new Date().toISOString(),
    })
    const local = bumpDraftDocument(server, { model: 'blank' })
    const result = await persistStudioDraft({
      userId: 'u1',
      designId: 'd1',
      document: local,
      fingerprint: draftContentFingerprint(local),
      lastSyncedFingerprint: null,
      expectedRevision: 1, // stale vs server.clientRevision
    })
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.conflict).not.toBeNull()
      expect(result.conflict?.server.strokes).toHaveLength(1)
    }
  })

  it('reconciles a lost create response without spawning a second draft', async () => {
    api.failCreateOnce = true
    const doc = strokedDoc()
    const result = await persistStudioDraft({
      userId: 'u1',
      designId: null,
      document: doc,
      fingerprint: draftContentFingerprint(doc),
      lastSyncedFingerprint: null,
      expectedRevision: null,
    })
    expect(result.ok).toBe(true)
    expect(api.designs.size).toBe(1)
    if (result.ok) {
      expect(result.designId).toBe('design-recovered')
    }
  })

  it('strips custom reference URLs from cloud payloads', async () => {
    const doc = bumpDraftDocument(createEmptyDraftDocument(), {
      model: 'custom',
      customReferenceUrl: '/static/uploads/secret.png',
      customReferenceKey: 'uploads/secret.png',
    })
    const result = await persistStudioDraft({
      userId: 'u1',
      designId: null,
      document: doc,
      fingerprint: draftContentFingerprint(doc),
      lastSyncedFingerprint: null,
      expectedRevision: null,
    })
    expect(result.ok).toBe(true)
    const stored = [...api.designs.values()][0]!
    expect(stored.design_data.customReferenceUrl).toBeNull()
    expect(stored.design_data.customReferenceKey).toBeNull()
  })
})
