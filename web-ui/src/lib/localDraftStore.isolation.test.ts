import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createEmptyDraftDocument } from '@/lib/draftDocument'

/**
 * Minimal in-memory IndexedDB stub keyed like production (object store keyPath = userId).
 * Proves account artwork cannot be read under another user id after a switch.
 */
function installMemoryIndexedDb() {
  const stores = new Map<string, Map<string, unknown>>()

  class MemoryRequest<T> {
    result: T | undefined
    error: DOMException | null = null
    onsuccess: ((ev: Event) => void) | null = null
    onerror: ((ev: Event) => void) | null = null
    _succeed(value: T) {
      this.result = value
      queueMicrotask(() => this.onsuccess?.(new Event('success')))
    }
    _fail(err: DOMException) {
      this.error = err
      queueMicrotask(() => this.onerror?.(new Event('error')))
    }
  }

  class MemoryTx {
    oncomplete: ((ev: Event) => void) | null = null
    onerror: ((ev: Event) => void) | null = null
    onabort: ((ev: Event) => void) | null = null
    error: DOMException | null = null
    private store: MemoryStore
    constructor(store: MemoryStore) {
      this.store = store
      queueMicrotask(() => this.oncomplete?.(new Event('complete')))
    }
    objectStore() {
      return this.store
    }
  }

  class MemoryStore {
    private data: Map<string, unknown>
    constructor(data: Map<string, unknown>) {
      this.data = data
    }
    get(key: string) {
      const req = new MemoryRequest<unknown>()
      req._succeed(this.data.get(key))
      return req
    }
    put(value: { userId: string }) {
      const req = new MemoryRequest<unknown>()
      this.data.set(value.userId, value)
      req._succeed(value)
      return req
    }
    delete(key: string) {
      const req = new MemoryRequest<undefined>()
      this.data.delete(key)
      req._succeed(undefined)
      return req
    }
  }

  class MemoryDb {
    objectStoreNames = { contains: (n: string) => n === 'drafts' }
    close() {}
    transaction(_store: string, _mode: string) {
      if (!stores.has('drafts')) stores.set('drafts', new Map())
      return new MemoryTx(new MemoryStore(stores.get('drafts')!))
    }
  }

  const idb = {
    open(_name: string, _version: number) {
      const req = new MemoryRequest<MemoryDb>()
      ;(req as MemoryRequest<MemoryDb> & { onupgradeneeded: ((ev: Event) => void) | null }).onupgradeneeded =
        null
      queueMicrotask(() => {
        if (!stores.has('drafts')) stores.set('drafts', new Map())
        req._succeed(new MemoryDb())
      })
      return req as MemoryRequest<MemoryDb> & {
        onupgradeneeded: ((ev: Event) => void) | null
      }
    },
  }

  vi.stubGlobal('indexedDB', idb)
  return {
    dump: () => stores.get('drafts') ?? new Map(),
  }
}

describe('localDraftStore user isolation', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
    vi.resetModules()
  })

  it('stores drafts per userId and never returns another account artwork', async () => {
    installMemoryIndexedDb()
    const { writeLocalDraft, readLocalDraft } = await import('@/lib/localDraftStore')

    const stampedA = { ...createEmptyDraftDocument(), clientRevision: 2 }

    await writeLocalDraft({
      userId: 'user-a',
      designId: 'design-a',
      document: stampedA,
      savedAt: '2026-10-20T12:00:00.000Z',
      syncedRevision: 1,
    })

    await writeLocalDraft({
      userId: 'user-b',
      designId: 'design-b',
      document: { ...createEmptyDraftDocument(), clientRevision: 1 },
      savedAt: '2026-10-20T12:01:00.000Z',
      syncedRevision: null,
    })

    const readA = await readLocalDraft('user-a')
    const readB = await readLocalDraft('user-b')
    const missing = await readLocalDraft('user-c')

    expect(readA?.designId).toBe('design-a')
    expect(readA?.document.clientRevision).toBe(2)
    expect(readB?.designId).toBe('design-b')
    expect(readB?.designId).not.toBe('design-a')
    expect(missing).toBeNull()
  })

  it('after account switch, the new user does not see the previous account draft', async () => {
    installMemoryIndexedDb()
    const { writeLocalDraft, readLocalDraft } = await import('@/lib/localDraftStore')

    await writeLocalDraft({
      userId: 'previous-account',
      designId: 'secret-art',
      document: { ...createEmptyDraftDocument(), clientRevision: 5 },
      savedAt: '2026-10-20T12:00:00.000Z',
      syncedRevision: 5,
    })

    // Simulate Studio remount keyed by the newly authenticated user id.
    const activeUserId = 'new-account'
    const shown = await readLocalDraft(activeUserId)
    expect(shown).toBeNull()

    const previousStillIsolated = await readLocalDraft('previous-account')
    expect(previousStillIsolated?.designId).toBe('secret-art')
  })
})
