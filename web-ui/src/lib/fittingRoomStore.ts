/**
 * Device-private Fitting Room assets (F1 person photo + F2 clothing).
 * IndexedDB only — no server upload until try-on enqueue.
 */

const DB_NAME = 'fashionrise-fitting-room'
const DB_VERSION = 1
const STORE = 'assets'

export type FittingRoomAssetKind = 'person' | 'garment'

export type FittingRoomAssetRecord = {
  /** `${userId}:${kind}` */
  key: string
  userId: string
  kind: FittingRoomAssetKind
  /** data URL (image/png or image/jpeg) */
  dataUrl: string
  mimeType: string
  updatedAt: string
  garmentCategory?: string
}

function assetKey(userId: string, kind: FittingRoomAssetKind): string {
  return `${userId}:${kind}`
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
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: 'key' })
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
      const tx = db.transaction(STORE, 'readonly')
      const req = tx.objectStore(STORE).get(assetKey(userId, kind))
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
    const tx = db.transaction(STORE, 'readwrite')
    tx.objectStore(STORE).put(full)
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
      const tx = db.transaction(STORE, 'readwrite')
      tx.objectStore(STORE).delete(assetKey(userId, kind))
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

/** Read a local File into a compressed-ish data URL for private storage. */
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
