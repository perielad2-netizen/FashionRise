import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createEmptyDraftDocument } from '@/lib/draftDocument'
import { writeLocalDraft } from '@/lib/localDraftStore'

describe('localDraftStore write results', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  it('returns ok:false when IndexedDB is unavailable', async () => {
    vi.stubGlobal('indexedDB', undefined)
    const result = await writeLocalDraft({
      userId: 'u1',
      designId: null,
      document: createEmptyDraftDocument(),
      savedAt: new Date().toISOString(),
      syncedRevision: null,
    })
    expect(result).toEqual({ ok: false, error: 'IndexedDB unavailable' })
  })
})
