/**
 * Device-private Fitting Room state (F1–F5).
 * IndexedDB only — person/outfit/saved results stay on-device until try-on enqueue.
 */

const DB_NAME = 'fashionrise-fitting-room'
const DB_VERSION = 2
const ASSETS = 'assets'
const OUTFIT = 'outfit'
const SAVED = 'saved'

export type FittingRoomAssetKind = 'person' | 'garment'

export type FittingRoomAssetRecord = {
  key: string
  userId: string
  kind: FittingRoomAssetKind
  dataUrl: string
  mimeType: string
  updatedAt: string
  garmentCategory?: string
}

export type FittingRoomOutfitPiece = {
  id: string
  category: string
  dataUrl: string
  mimeType: string
  updatedAt: string
}

export type FittingRoomOutfitSession = {
  key: string
  userId: string
  pieces: FittingRoomOutfitPiece[]
  updatedAt: string
}

export type FittingRoomSavedResult = {
  id: string
  userId: string
  jobId: string
  dataUrl: string
  label: string
  outfitCategories: string[]
  createdAt: string
}

function assetKey(userId: string, kind: FittingRoomAssetKind): string {
  return `${userId}:${kind}`
}

function outfitKey(userId: string): string {
  return `${userId}:outfit`
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') {
      reject(new Error('IndexedDB unavailable'))
      return
    }
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(ASSETS)) {
        db.createObjectStore(ASSETS, { keyPath: 'key' })
      }
      if (!db.objectStoreNames.contains(OUTFIT)) {
        db.createObjectStore(OUTFIT, { keyPath: 'key' })
      }
      if (!db.objectStoreNames.contains(SAVED)) {
        const store = db.createObjectStore(SAVED, { keyPath: 'id' })
        store.createIndex('byUser', 'userId', { unique: false })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error ?? new Error('IndexedDB open failed'))
  })
}

export async function readFittingRoomAsset(
  userId: string,
  kind: FittingRoomAssetKind,
): Promise<FittingRoomAssetRecord | null> {
  try {
    const db = await openDb()
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(ASSETS, 'readonly')
      const req = tx.objectStore(ASSETS).get(assetKey(userId, kind))
      req.onsuccess = () => resolve((req.result as FittingRoomAssetRecord | undefined) ?? null)
      req.onerror = () => reject(req.error)
      tx.oncomplete = () => db.close()
    })
  } catch {
    return null
  }
}

export async function writeFittingRoomAsset(
  record: Omit<FittingRoomAssetRecord, 'key'> & { key?: string },
): Promise<void> {
  const db = await openDb()
  const full: FittingRoomAssetRecord = {
    ...record,
    key: assetKey(record.userId, record.kind),
  }
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(ASSETS, 'readwrite')
    tx.objectStore(ASSETS).put(full)
    tx.oncomplete = () => {
      db.close()
      resolve()
    }
    tx.onerror = () => reject(tx.error)
  })
}

export async function deleteFittingRoomAsset(
  userId: string,
  kind: FittingRoomAssetKind,
): Promise<void> {
  try {
    const db = await openDb()
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(ASSETS, 'readwrite')
      tx.objectStore(ASSETS).delete(assetKey(userId, kind))
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

export async function readOutfitSession(userId: string): Promise<FittingRoomOutfitSession | null> {
  try {
    const db = await openDb()
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(OUTFIT, 'readonly')
      const req = tx.objectStore(OUTFIT).get(outfitKey(userId))
      req.onsuccess = () => resolve((req.result as FittingRoomOutfitSession | undefined) ?? null)
      req.onerror = () => reject(req.error)
      tx.oncomplete = () => db.close()
    })
  } catch {
    return null
  }
}

export async function writeOutfitSession(session: FittingRoomOutfitSession): Promise<void> {
  const db = await openDb()
  const full: FittingRoomOutfitSession = {
    ...session,
    key: outfitKey(session.userId),
  }
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(OUTFIT, 'readwrite')
    tx.objectStore(OUTFIT).put(full)
    tx.oncomplete = () => {
      db.close()
      resolve()
    }
    tx.onerror = () => reject(tx.error)
  })
}

export async function clearOutfitSession(userId: string): Promise<void> {
  try {
    const db = await openDb()
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(OUTFIT, 'readwrite')
      tx.objectStore(OUTFIT).delete(outfitKey(userId))
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

export async function listSavedResults(userId: string): Promise<FittingRoomSavedResult[]> {
  try {
    const db = await openDb()
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(SAVED, 'readonly')
      const idx = tx.objectStore(SAVED).index('byUser')
      const req = idx.getAll(userId)
      req.onsuccess = () => {
        const rows = (req.result as FittingRoomSavedResult[]) || []
        rows.sort((a, b) => b.createdAt.localeCompare(a.createdAt))
        resolve(rows)
      }
      req.onerror = () => reject(req.error)
      tx.oncomplete = () => db.close()
    })
  } catch {
    return []
  }
}

export async function saveFittingResult(
  record: FittingRoomSavedResult,
): Promise<void> {
  const db = await openDb()
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(SAVED, 'readwrite')
    tx.objectStore(SAVED).put(record)
    tx.oncomplete = () => {
      db.close()
      resolve()
    }
    tx.onerror = () => reject(tx.error)
  })
}

export async function deleteSavedResult(id: string): Promise<void> {
  try {
    const db = await openDb()
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(SAVED, 'readwrite')
      tx.objectStore(SAVED).delete(id)
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

export function fileToFittingRoomDataUrl(file: File): Promise<{ dataUrl: string; mimeType: string }> {
  return new Promise((resolve, reject) => {
    if (!file.type.startsWith('image/')) {
      reject(new Error('Please choose a photo or clothing image.'))
      return
    }
    const reader = new FileReader()
    reader.onload = () => {
      const dataUrl = typeof reader.result === 'string' ? reader.result : ''
      if (!dataUrl.startsWith('data:image/')) {
        reject(new Error('Could not read that image.'))
        return
      }
      resolve({ dataUrl, mimeType: file.type || 'image/jpeg' })
    }
    reader.onerror = () => reject(reader.error ?? new Error('Could not read that image.'))
    reader.readAsDataURL(file)
  })
}

export function newOutfitPieceId(): string {
  return `piece_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
}
