import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  bumpDraftDocument,
  createEmptyDraftDocument,
  draftContentFingerprint,
} from '@/lib/draftDocument'
import {
  persistLocalRecovery,
  persistStudioDraft,
  restoreStudioDraft,
} from '@/lib/draftPersistence'
import type { StudioDraftDocument } from '@/lib/draftDocument'
import { documentForCloud } from '@/services/designsApi'

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
    const existing = localStore.records.get(record.userId) as
      | {
          document: StudioDraftDocument
          designId: string | null
          syncedRevision: number | null
          savedAt: string
        }
      | undefined
    if (existing && existing.document.clientRevision > record.document.clientRevision) {
      localStore.records.set(record.userId, {
        ...existing,
        designId: record.designId ?? existing.designId,
      })
      return { ok: true, wrote: false, reason: 'stale' }
    }
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
  designs: new Map<
    string,
    {
      id: string
      design_data: StudioDraftDocument | Record<string, unknown>
      metadata: Record<string, unknown>
      visibility: string
      updated_at: string
    }
  >(),
  failCreateOnce: false,
  failUpdateStatus: null as number | null,
  createCalls: 0,
  updateCalls: [] as Array<{
    id: string
    expected?: number | null
    clearBackIntent?: boolean
    metadata?: Record<string, unknown>
  }>,
  updateGate: null as Promise<void> | null,
  updateGateModel: null as string | null,
  /** Runs after list-empty and immediately before create — inject a raced draft here. */
  onBeforeCreate: null as null | (() => void),
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
        design_data: d.design_data as unknown as Record<string, unknown>,
        metadata: d.metadata,
        visibility: d.visibility,
        status: 'draft',
        created_at: d.updated_at,
        updated_at: d.updated_at,
      }
    },
    createStudioDraft: async (document: StudioDraftDocument) => {
      api.onBeforeCreate?.()
      api.createCalls += 1
      const cloud = actual.documentForCloud(document)
      const existing = [...api.designs.values()].find(
        (d) => d.metadata.draftKind === 'studio_working_draft',
      )
      if (existing) {
        const sameFp =
          draftContentFingerprint(actual.documentForCloud(existing.design_data)) ===
          draftContentFingerprint(cloud)
        if (sameFp) {
          return {
            id: existing.id,
            user_id: 'u1',
            title: 'Studio working draft',
            description: null,
            garment_category: 'studio',
            design_data: existing.design_data as unknown as Record<string, unknown>,
            metadata: existing.metadata,
            visibility: 'private',
            status: 'draft',
            created_at: existing.updated_at,
            updated_at: existing.updated_at,
          }
        }
        const { ApiError } = await import('@/services/api/client')
        throw new ApiError('Studio working draft already exists with different content.', 409, {
          detail: {
            code: 'conflict',
            message: 'Studio working draft already exists with different content.',
            payload: {
              expected_revision: cloud.clientRevision,
              current_revision: existing.design_data.clientRevision,
              design: {
                id: existing.id,
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
      if (api.failCreateOnce) {
        api.failCreateOnce = false
        const id = 'design-recovered'
        api.designs.set(id, {
          id,
          design_data: cloud,
          metadata: { draftKind: 'studio_working_draft', clientRevision: cloud.clientRevision },
          visibility: 'private',
          updated_at: new Date().toISOString(),
        })
        throw new Error('network dropped after create')
      }
      const id = `design-${api.createCalls}`
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
      if (api.updateGate && api.updateGateModel && document.model === api.updateGateModel) {
        await api.updateGate
      }
      if (api.failUpdateStatus != null) {
        const status = api.failUpdateStatus
        api.failUpdateStatus = null
        const { ApiError } = await import('@/services/api/client')
        throw new ApiError(status === 503 ? 'server down' : 'error', status, null)
      }
      const metadata = actual.cloudDraftMetadata(document)
      api.updateCalls.push({
        id: designId,
        expected: options?.expectedRevision,
        clearBackIntent: Boolean(document.clearBackIntent),
        metadata,
      })
      const existing = api.designs.get(designId)
      if (!existing) {
        const { ApiError } = await import('@/services/api/client')
        throw new ApiError('missing', 404, null)
      }
      const currentRevision = (existing.design_data as { clientRevision?: unknown }).clientRevision
      if (
        options?.expectedRevision != null &&
        currentRevision !== options.expectedRevision
      ) {
        const { ApiError } = await import('@/services/api/client')
        throw new ApiError('conflict', 409, {
          detail: {
            code: 'conflict',
            message: 'Draft was updated elsewhere.',
            payload: {
              expected_revision: options.expectedRevision,
              current_revision: currentRevision,
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
      existing.metadata = {
        ...metadata,
        draftKind: 'studio_working_draft',
        clientRevision: cloud.clientRevision,
      }
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

describe('draftPersistence WEB-V2.1A/B', () => {
  beforeEach(() => {
    localStore.records.clear()
    localStore.designIds.clear()
    localStore.failWrites = false
    api.designs.clear()
    api.failCreateOnce = false
    api.failUpdateStatus = null
    api.createCalls = 0
    api.updateCalls = []
    api.updateGate = null
    api.updateGateModel = null
    api.onBeforeCreate = null
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
      expectedRevision: 1,
    })
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.conflict).not.toBeNull()
      expect(result.conflict?.server.strokes).toHaveLength(1)
    }
  })

  it('treats same-content 409 as ACK (lost response) without conflict', async () => {
    const doc = strokedDoc()
    api.designs.set('d1', {
      id: 'd1',
      design_data: doc,
      metadata: { draftKind: 'studio_working_draft', clientRevision: doc.clientRevision },
      visibility: 'private',
      updated_at: new Date().toISOString(),
    })
    // Stale expected token but identical cloud content → 409 payload, recovered as ACK.
    const result = await persistStudioDraft({
      userId: 'u1',
      designId: 'd1',
      document: doc,
      fingerprint: draftContentFingerprint(documentForCloud(doc)),
      lastSyncedFingerprint: null,
      expectedRevision: Math.max(1, doc.clientRevision - 1),
    })
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.designId).toBe('d1')
      expect(result.syncedRevision).toBe(doc.clientRevision)
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

  it('does not let a delayed cloud response for edit A overwrite local recovery for edit B', async () => {
    const editA = strokedDoc()
    api.designs.set('d1', {
      id: 'd1',
      design_data: createEmptyDraftDocument(),
      metadata: { draftKind: 'studio_working_draft', clientRevision: 1 },
      visibility: 'private',
      updated_at: new Date().toISOString(),
    })

    let releaseA!: () => void
    api.updateGate = new Promise<void>((resolve) => {
      releaseA = resolve
    })
    api.updateGateModel = 'male'

    const saveA = persistStudioDraft({
      userId: 'u1',
      designId: 'd1',
      document: editA,
      fingerprint: draftContentFingerprint(editA),
      lastSyncedFingerprint: null,
      expectedRevision: 1,
    })

    const editB = bumpDraftDocument(editA, { model: 'blank', dimmed: true })
    await persistLocalRecovery({
      userId: 'u1',
      designId: 'd1',
      document: editB,
      syncedRevision: 1,
    })

    releaseA()
    await saveA

    const recovered = localStore.records.get('u1') as { document: StudioDraftDocument }
    expect(recovered.document.model).toBe('blank')
    expect(recovered.document.dimmed).toBe(true)
    expect(recovered.document.clientRevision).toBe(editB.clientRevision)
  })

  it('preserves server-acknowledged revision when fingerprint matches after edit→revert', async () => {
    const base = createEmptyDraftDocument()
    const edited = bumpDraftDocument(base, { model: 'male-straight' })
    const reverted = bumpDraftDocument(edited, { model: 'female-straight' })
    expect(draftContentFingerprint(documentForCloud(reverted))).toBe(
      draftContentFingerprint(documentForCloud(base)),
    )

    const result = await persistStudioDraft({
      userId: 'u1',
      designId: 'd1',
      document: reverted,
      fingerprint: draftContentFingerprint(documentForCloud(reverted)),
      lastSyncedFingerprint: draftContentFingerprint(documentForCloud(base)),
      expectedRevision: 1,
    })
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.syncedRevision).toBe(1)
      expect(result.syncedRevision).not.toBe(reverted.clientRevision)
    }
  })

  it('createOnly opens a brand-new account without adopting another draft', async () => {
    const doc = strokedDoc()
    const result = await persistStudioDraft({
      userId: 'u1',
      designId: null,
      document: doc,
      fingerprint: draftContentFingerprint(doc),
      lastSyncedFingerprint: null,
      expectedRevision: null,
      createOnly: true,
    })
    expect(result.ok).toBe(true)
    expect(api.designs.size).toBe(1)
    expect(api.updateCalls).toHaveLength(0)
  })

  it('createOnly refuses a draft that appears between list and create', async () => {
    const openDoc = strokedDoc()
    const foreign = bumpDraftDocument(createEmptyDraftDocument(), {
      model: 'blank',
      strokes: [
        {
          id: 'other-device',
          tool: 'draw',
          points: [1, 1, 0.5],
          color: '#1C1C1E',
          size: 2,
          opacity: 1,
        },
      ],
    })
    api.onBeforeCreate = () => {
      api.designs.set('foreign', {
        id: 'foreign',
        design_data: foreign,
        metadata: { draftKind: 'studio_working_draft', clientRevision: foreign.clientRevision },
        visibility: 'private',
        updated_at: new Date().toISOString(),
      })
    }

    const result = await persistStudioDraft({
      userId: 'u1',
      designId: null,
      document: openDoc,
      fingerprint: draftContentFingerprint(openDoc),
      lastSyncedFingerprint: null,
      expectedRevision: null,
      createOnly: true,
    })
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.conflict?.designId).toBe('foreign')
      expect(result.conflict?.server.strokes[0]?.id).toBe('other-device')
    }
    expect(api.designs.get('foreign')!.design_data.strokes[0]!.id).toBe('other-device')
    expect(api.updateCalls).toHaveLength(0)
  })

  it('createOnly preserves an existing different draft found before create', async () => {
    const foreign = bumpDraftDocument(createEmptyDraftDocument(), { model: 'blank' })
    api.designs.set('foreign', {
      id: 'foreign',
      design_data: foreign,
      metadata: { draftKind: 'studio_working_draft', clientRevision: foreign.clientRevision },
      visibility: 'private',
      updated_at: new Date().toISOString(),
    })
    const openDoc = strokedDoc()
    const result = await persistStudioDraft({
      userId: 'u1',
      designId: null,
      document: openDoc,
      fingerprint: draftContentFingerprint(openDoc),
      lastSyncedFingerprint: null,
      expectedRevision: null,
      createOnly: true,
    })
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.conflict?.designId).toBe('foreign')
    expect(api.designs.get('foreign')!.design_data.model).toBe('blank')
    expect(api.updateCalls).toHaveLength(0)
    expect(api.createCalls).toBe(0)
  })

  it('createOnly recovers a lost create response with matching content', async () => {
    api.failCreateOnce = true
    const doc = strokedDoc()
    const result = await persistStudioDraft({
      userId: 'u1',
      designId: null,
      document: doc,
      fingerprint: draftContentFingerprint(doc),
      lastSyncedFingerprint: null,
      expectedRevision: null,
      createOnly: true,
    })
    expect(result.ok).toBe(true)
    expect(api.designs.size).toBe(1)
    expect(api.updateCalls).toHaveLength(0)
    if (result.ok) expect(result.designId).toBe('design-recovered')
  })

  it('autosave without createOnly still adopts an existing draft via OCC update', async () => {
    const existing = bumpDraftDocument(createEmptyDraftDocument(), { model: 'blank' })
    api.designs.set('d1', {
      id: 'd1',
      design_data: existing,
      metadata: { draftKind: 'studio_working_draft', clientRevision: existing.clientRevision },
      visibility: 'private',
      updated_at: new Date().toISOString(),
    })
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
    expect(api.updateCalls).toHaveLength(1)
    expect(api.updateCalls[0]?.id).toBe('d1')
    expect(api.updateCalls[0]?.expected).toBe(existing.clientRevision)
    expect(api.designs.get('d1')!.design_data.model).toBe('male')
  })

  it('does not blind-reconcile when preferred design update fails with a non-409 error', async () => {
    api.designs.set('d1', {
      id: 'd1',
      design_data: createEmptyDraftDocument(),
      metadata: { draftKind: 'studio_working_draft', clientRevision: 1 },
      visibility: 'private',
      updated_at: new Date().toISOString(),
    })
    api.designs.set('d2', {
      id: 'd2',
      design_data: bumpDraftDocument(createEmptyDraftDocument(), { model: 'blank' }),
      metadata: { draftKind: 'studio_working_draft', clientRevision: 9 },
      visibility: 'private',
      updated_at: new Date().toISOString(),
    })
    api.failUpdateStatus = 503

    const doc = strokedDoc()
    const result = await persistStudioDraft({
      userId: 'u1',
      designId: 'd1',
      document: doc,
      fingerprint: draftContentFingerprint(doc),
      lastSyncedFingerprint: null,
      expectedRevision: 1,
    })
    expect(result.ok).toBe(false)
    expect((api.designs.get('d1')!.design_data as StudioDraftDocument).model).toBe('female-straight')
    expect((api.designs.get('d2')!.design_data as StudioDraftDocument).model).toBe('blank')
    expect(api.updateCalls).toHaveLength(0)
  })
})

function malformedCloudV2(overrides: Record<string, unknown> = {}): Record<string, unknown> {
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
    // Present malformed Back — strict parse must reject the whole document.
    back: { strokes: 'not-an-array', fills: [] },
    model: 'female-straight',
    customReferenceUrl: null,
    customReferenceKey: null,
    brush: { sizeId: 'thin', opacity: 1, color: '#1C1C1E' },
    dimmed: false,
    clientRevision: 4,
    updatedAt: '2026-10-25T00:00:00.000Z',
    ...overrides,
  }
}

describe('restoreStudioDraft damaged cloud V2 safety', () => {
  beforeEach(() => {
    localStore.records.clear()
    localStore.designIds.clear()
    localStore.failWrites = false
    api.designs.clear()
    api.failCreateOnce = false
    api.failUpdateStatus = null
    api.createCalls = 0
    api.updateCalls = []
    api.updateGate = null
    api.updateGateModel = null
    api.onBeforeCreate = null
  })

  it('treats an unreadable cloud V2 row as damaged (not missing) when there is no local copy', async () => {
    const raw = malformedCloudV2()
    api.designs.set('cloud-bad', {
      id: 'cloud-bad',
      design_data: raw,
      metadata: { draftKind: 'studio_working_draft', clientRevision: 4, schema: 'fashionrise.studio.draft.v2' },
      visibility: 'private',
      updated_at: '2026-10-25T00:00:00.000Z',
    })
    localStore.designIds.set('u1', 'cloud-bad')

    const restored = await restoreStudioDraft('u1')
    expect(restored.damagedCloud?.designId).toBe('cloud-bad')
    expect(restored.damagedCloud?.rawDesign.design_data).toEqual(raw)
    expect(restored.blockAutomaticCloudWrites).toBe(true)
    expect(restored.conflict).toBeNull()
    expect(restored.notice).toMatch(/could not be read/i)
    expect(restored.notice).not.toMatch(/Syncing/i)
    expect(api.createCalls).toBe(0)
    expect(api.updateCalls).toHaveLength(0)
    // Must not invent a durable local overwrite during restore.
    expect(localStore.records.has('u1')).toBe(false)
  })

  it('preserves a stale local recovery doc and blocks automatic PUT/POST over damaged cloud V2', async () => {
    const raw = malformedCloudV2({ clientRevision: 9 })
    const local = strokedDoc()
    localStore.records.set('u1', {
      userId: 'u1',
      designId: 'cloud-bad',
      document: local,
      savedAt: '2026-10-24T00:00:00.000Z',
      syncedRevision: 2,
    })
    localStore.designIds.set('u1', 'cloud-bad')
    api.designs.set('cloud-bad', {
      id: 'cloud-bad',
      design_data: raw,
      metadata: { draftKind: 'studio_working_draft', clientRevision: 9, schema: 'fashionrise.studio.draft.v2' },
      visibility: 'private',
      updated_at: '2026-10-25T00:00:00.000Z',
    })

    const restored = await restoreStudioDraft('u1')
    expect(restored.blockAutomaticCloudWrites).toBe(true)
    expect(restored.damagedCloud?.hasLocalRecovery).toBe(true)
    expect(restored.document.strokes).toEqual(local.strokes)
    expect(restored.notice).not.toMatch(/Syncing/i)
    expect(api.createCalls).toBe(0)
    expect(api.updateCalls).toHaveLength(0)
    // Local recovery row preserved (not replaced with empty / cloud-derived doc).
    const kept = localStore.records.get('u1') as { document: StudioDraftDocument }
    expect(kept.document.strokes).toEqual(local.strokes)
    expect(api.designs.get('cloud-bad')!.design_data).toEqual(raw)

    // Explicit autosave path must still be a deliberate recovery call — restore itself never wrote.
    const unsyncedAttempt = await persistStudioDraft({
      userId: 'u1',
      designId: 'cloud-bad',
      document: local,
      fingerprint: draftContentFingerprint(local),
      lastSyncedFingerprint: null,
      expectedRevision: null,
    })
    // Without an expected revision token from operator recovery, prefer-id update cannot
    // extract the damaged row and must not blind-create a second draft.
    expect(unsyncedAttempt.ok).toBe(false)
    expect(api.designs.get('cloud-bad')!.design_data).toEqual(raw)
  })

  it('keeps offline / missing-server local restore behavior unchanged', async () => {
    const local = strokedDoc()
    localStore.records.set('u1', {
      userId: 'u1',
      designId: null,
      document: local,
      savedAt: new Date().toISOString(),
      syncedRevision: null,
    })
    const restored = await restoreStudioDraft('u1')
    expect(restored.damagedCloud).toBeNull()
    expect(restored.blockAutomaticCloudWrites).toBe(false)
    expect(restored.document.strokes).toHaveLength(1)
    expect(restored.notice).toMatch(/Syncing/i)
  })

  it('forwards clearBackIntent metadata through Front clear → Back clear save (no false conflict)', async () => {
    // Seed cloud draft with Front + Back ink at revision 2.
    let seed = createEmptyDraftDocument()
    seed = bumpDraftDocument(seed, {
      schema: 'fashionrise.studio.draft.v2',
      activeSide: 'front',
      strokes: [
        {
          id: 'f1',
          tool: 'draw',
          points: [10, 20, 0.5, 30, 40, 0.5],
          color: '#1C1C1E',
          size: 2,
          opacity: 1,
        },
      ],
      back: {
        strokes: [
          {
            id: 'b1',
            tool: 'draw',
            points: [50, 60, 0.5, 70, 80, 0.5],
            color: '#1C1C1E',
            size: 2,
            opacity: 1,
          },
        ],
        fills: [],
      },
      model: 'female-straight',
    })
    api.designs.set('draft-1', {
      id: 'draft-1',
      design_data: documentForCloud(seed),
      metadata: {
        draftKind: 'studio_working_draft',
        clientRevision: seed.clientRevision,
        schema: 'fashionrise.studio.draft.v2',
      },
      visibility: 'private',
      updated_at: new Date().toISOString(),
    })
    localStore.designIds.set('u1', 'draft-1')

    // Clear Front (no clearBackIntent).
    const frontCleared = bumpDraftDocument(seed, {
      strokes: [],
      fills: [],
      activeSide: 'front',
    })
    const frontSave = await persistStudioDraft({
      userId: 'u1',
      designId: 'draft-1',
      document: frontCleared,
      fingerprint: draftContentFingerprint(documentForCloud(frontCleared)),
      lastSyncedFingerprint: draftContentFingerprint(documentForCloud(seed)),
      expectedRevision: seed.clientRevision,
    })
    expect(frontSave.ok).toBe(true)
    expect(api.updateCalls.at(-1)?.clearBackIntent).toBe(false)

    // Clear Back with explicit intent — must reach metadata (regression for false 409).
    const backCleared: StudioDraftDocument = {
      ...bumpDraftDocument(frontCleared, {
        activeSide: 'back',
        back: { strokes: [], fills: [] },
        clearBackIntent: true,
      }),
      clearBackIntent: true,
    }
    expect(backCleared.clearBackIntent).toBe(true)
    expect(documentForCloud(backCleared).clearBackIntent).toBeUndefined()

    const backSave = await persistStudioDraft({
      userId: 'u1',
      designId: 'draft-1',
      document: backCleared,
      fingerprint: draftContentFingerprint(documentForCloud(backCleared)),
      lastSyncedFingerprint: frontSave.ok ? frontSave.fingerprint : null,
      expectedRevision: frontSave.ok ? frontSave.syncedRevision : null,
    })
    expect(backSave.ok).toBe(true)
    expect(backSave.conflict).toBeFalsy()
    const last = api.updateCalls.at(-1)
    expect(last?.clearBackIntent).toBe(true)
    expect(last?.metadata?.clearBackIntent).toBe(true)
    expect(last?.expected).toBe(frontCleared.clientRevision)

    const stored = api.designs.get('draft-1')!
    const storedDoc = stored.design_data as StudioDraftDocument
    expect(storedDoc.strokes).toEqual([])
    expect(storedDoc.back?.strokes ?? []).toEqual([])
    expect(stored.metadata.clearBackIntent).toBe(true)
  })

  it('still surfaces a real two-tab OCC conflict when revisions diverge', async () => {
    const local = strokedDoc()
    api.designs.set('draft-occ', {
      id: 'draft-occ',
      design_data: documentForCloud(local),
      metadata: { draftKind: 'studio_working_draft', clientRevision: local.clientRevision },
      visibility: 'private',
      updated_at: new Date().toISOString(),
    })
    // Another tab already advanced the server revision.
    const other = bumpDraftDocument(local, {
      strokes: [
        {
          id: 'other',
          tool: 'draw',
          points: [1, 2, 0.5, 3, 4, 0.5],
          color: '#FF0000',
          size: 2,
          opacity: 1,
        },
      ],
    })
    api.designs.set('draft-occ', {
      id: 'draft-occ',
      design_data: documentForCloud(other),
      metadata: { draftKind: 'studio_working_draft', clientRevision: other.clientRevision },
      visibility: 'private',
      updated_at: new Date().toISOString(),
    })

    const mine = bumpDraftDocument(local, {
      strokes: [
        {
          id: 'mine',
          tool: 'draw',
          points: [9, 9, 0.5, 8, 8, 0.5],
          color: '#00FF00',
          size: 2,
          opacity: 1,
        },
      ],
    })
    const result = await persistStudioDraft({
      userId: 'u1',
      designId: 'draft-occ',
      document: mine,
      fingerprint: draftContentFingerprint(documentForCloud(mine)),
      lastSyncedFingerprint: draftContentFingerprint(documentForCloud(local)),
      expectedRevision: local.clientRevision,
    })
    expect(result.ok).toBe(false)
    expect(result.conflict).toBeTruthy()
    expect(result.conflict?.server.strokes[0]?.id).toBe('other')
  })
})
