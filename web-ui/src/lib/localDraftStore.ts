import type { StudioDraftDocument } from '@/lib/draftDocument'

const DB_NAME = 'fashionrise-studio'
const DB_VERSION = 1
const STORE = 'drafts'

export type LocalDraftRecord = {
  userId: string
  designId: string | null
  document: StudioDraftDocument
  savedAt: string
  /** Last known server revision successfully acknowledged. */
  syncedRevision: number | null
}

export type LocalWriteResult =
  | { ok: true }
  | { ok: false; error: string }

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') {
      reject(new Error('IndexedDB unavailable'))
      return
    }
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: 'userId' })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error ?? new Error('IndexedDB open failed'))
  })
}

export async function readLocalDraft(userId: string): Promise<LocalDraftRecord | null> {
  try {
    const db = await openDb()
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readonly')
      const req = tx.objectStore(STORE).get(userId)
      req.onsuccess = () => resolve((req.result as LocalDraftRecord | undefined) ?? null)
      req.onerror = () => reject(req.error)
      tx.oncomplete = () => db.close()
    })
  } catch {
    return null
  }
}

export async function writeLocalDraft(record: LocalDraftRecord): Promise<LocalWriteResult> {
  try {
    const db = await openDb()
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite')
      tx.objectStore(STORE).put(record)
      tx.oncomplete = () => {
        db.close()
        resolve()
      }
      tx.onerror = () => reject(tx.error ?? new Error('IndexedDB write failed'))
      tx.onabort = () => reject(tx.error ?? new Error('IndexedDB write aborted'))
    })
    return { ok: true }
  } catch (err) {
    const message =
      err instanceof DOMException && err.name === 'QuotaExceededError'
        ? 'Local storage quota exceeded'
        : err instanceof Error
          ? err.message
          : 'IndexedDB write failed'
    return { ok: false, error: message }
  }
}

export async function clearLocalDraft(userId: string): Promise<void> {
  try {
    const db = await openDb()
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite')
      tx.objectStore(STORE).delete(userId)
      tx.oncomplete = () => {
        db.close()
        resolve()
      }
      tx.onerror = () => reject(tx.error)
    })
  } catch {
    /* ignore */
  }
}

const DESIGN_ID_PREFIX = 'fr.studio.draftDesignId.'

export function readStoredDesignId(userId: string): string | null {
  try {
    return localStorage.getItem(`${DESIGN_ID_PREFIX}${userId}`)
  } catch {
    return null
  }
}

export function writeStoredDesignId(userId: string, designId: string): void {
  try {
    localStorage.setItem(`${DESIGN_ID_PREFIX}${userId}`, designId)
  } catch {
    /* ignore */
  }
}
