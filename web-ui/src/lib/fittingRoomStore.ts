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
  /** Set when planted from FashionRise Social Try on me. */
  source?: 'fashionrise_look' | 'upload'
  /** Social gallery item id when planted from FashionRise feed (designer Stars). */
  galleryItemId?: string
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

/** Long-edge cap — phone cameras + PNG bake otherwise blow past nginx body limits. */
export const FITTING_ROOM_MAX_EDGE_PX = 2048

/**
 * Soft max for one Fitting Room data URL (base64). Person + up to 4 garments travel
 * in one JSON POST; keep each plate under ~4 MB so the payload stays under the edge.
 */
export const FITTING_ROOM_DATA_URL_SOFT_MAX_CHARS = 4 * 1024 * 1024

function canvasToFittingRoomJpeg(
  canvas: HTMLCanvasElement,
): { dataUrl: string; mimeType: string } {
  let quality = 0.88
  let dataUrl = canvas.toDataURL('image/jpeg', quality)
  for (let i = 0; i < 6 && dataUrl.length > FITTING_ROOM_DATA_URL_SOFT_MAX_CHARS; i++) {
    quality = Math.max(0.5, quality - 0.08)
    dataUrl = canvas.toDataURL('image/jpeg', quality)
  }
  if (!dataUrl.startsWith('data:image/')) {
    throw new Error('Could not read that image.')
  }
  return { dataUrl, mimeType: 'image/jpeg' }
}

function drawFittingRoomBitmap(
  source: CanvasImageSource,
  srcW: number,
  srcH: number,
  maxEdge: number = FITTING_ROOM_MAX_EDGE_PX,
): HTMLCanvasElement {
  const scale = Math.min(1, maxEdge / Math.max(srcW, srcH, 1))
  const w = Math.max(1, Math.round(srcW * scale))
  const h = Math.max(1, Math.round(srcH * scale))
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Could not prepare that image.')
  // White fill — JPEG has no alpha; look plates with transparency stay readable.
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, w, h)
  ctx.drawImage(source, 0, 0, w, h)
  return canvas
}

/**
 * Re-encode an already-saved Fitting Room data URL under the try-on payload budget.
 * Needed for photos baked before compression existed (IndexedDB may hold huge PNGs).
 */
export async function compressFittingRoomDataUrl(
  dataUrl: string,
): Promise<{ dataUrl: string; mimeType: string }> {
  if (!dataUrl.startsWith('data:image/')) {
    throw new Error('Could not read that image.')
  }
  if (
    dataUrl.startsWith('data:image/jpeg') &&
    dataUrl.length <= FITTING_ROOM_DATA_URL_SOFT_MAX_CHARS
  ) {
    return { dataUrl, mimeType: 'image/jpeg' }
  }
  const img = await new Promise<HTMLImageElement>((resolve, reject) => {
    const el = new Image()
    el.onload = () => resolve(el)
    el.onerror = () => reject(new Error('Could not read that image.'))
    el.src = dataUrl
  })
  const srcW = img.naturalWidth || img.width
  const srcH = img.naturalHeight || img.height
  let edge = FITTING_ROOM_MAX_EDGE_PX
  let out = canvasToFittingRoomJpeg(drawFittingRoomBitmap(img, srcW, srcH, edge))
  for (let i = 0; i < 4 && out.dataUrl.length > FITTING_ROOM_DATA_URL_SOFT_MAX_CHARS; i++) {
    edge = Math.max(1024, Math.round(edge * 0.75))
    out = canvasToFittingRoomJpeg(drawFittingRoomBitmap(img, srcW, srcH, edge))
  }
  return out
}

/**
 * Read a Fitting Room photo/garment file as an upright JPEG data URL.
 * Bakes EXIF orientation into pixels so try-on providers don't get a 90° flip
 * (browsers show EXIF-corrected <img>, but raw JPEG bytes are often sideways).
 * JPEG + long-edge cap keeps phone photos under nginx try-on body limits.
 */
export async function fileToFittingRoomDataUrl(
  file: File,
): Promise<{ dataUrl: string; mimeType: string }> {
  if (!file.type.startsWith('image/')) {
    throw new Error('Please choose a photo or clothing image.')
  }

  const bakeFromBitmap = async (bitmap: ImageBitmap): Promise<{ dataUrl: string; mimeType: string }> => {
    const canvas = drawFittingRoomBitmap(bitmap, bitmap.width, bitmap.height)
    bitmap.close()
    return canvasToFittingRoomJpeg(canvas)
  }

  // Prefer createImageBitmap with EXIF orientation (Chrome/Android WebView).
  if (typeof createImageBitmap === 'function') {
    try {
      const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' } as ImageBitmapOptions)
      return await bakeFromBitmap(bitmap)
    } catch {
      try {
        const bitmap = await createImageBitmap(file)
        return await bakeFromBitmap(bitmap)
      } catch {
        /* fall through to FileReader */
      }
    }
  }

  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const dataUrl = typeof reader.result === 'string' ? reader.result : ''
      if (!dataUrl.startsWith('data:image/')) {
        reject(new Error('Could not read that image.'))
        return
      }
      // Last resort: decode via <img> + canvas (many engines apply EXIF on draw).
      const img = new Image()
      img.onload = () => {
        try {
          const canvas = drawFittingRoomBitmap(
            img,
            img.naturalWidth || img.width,
            img.naturalHeight || img.height,
          )
          resolve(canvasToFittingRoomJpeg(canvas))
        } catch (err) {
          reject(err instanceof Error ? err : new Error('Could not read that image.'))
        }
      }
      img.onerror = () => reject(new Error('Could not read that image.'))
      img.src = dataUrl
    }
    reader.onerror = () => reject(reader.error ?? new Error('Could not read that image.'))
    reader.readAsDataURL(file)
  })
}

export function newOutfitPieceId(): string {
  return `piece_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
}

/** sessionStorage key: FashionRise feed planted a look into Fitting Room. */
export const FITTING_ROOM_PLANTED_NOTICE_KEY = 'fr.fittingRoom.plantedFromFeed'

export type FittingRoomPlantedNotice = {
  title: string
  galleryItemId: string
  at: string
}

/**
 * Convert gallery/look image bytes into an upright PNG data URL for Fitting Room.
 */
export async function blobToFittingRoomDataUrl(
  blob: Blob,
): Promise<{ dataUrl: string; mimeType: string }> {
  const type = blob.type && blob.type.startsWith('image/') ? blob.type : 'image/png'
  const file = new File([blob], 'fashionrise-look.png', { type })
  return fileToFittingRoomDataUrl(file)
}

/**
 * Plant a single clothing piece from FashionRise Social into the device outfit
 * session (replaces prior pieces so the chosen look is clearly ready to try on).
 */
export async function plantFittingRoomGarment(opts: {
  userId: string
  dataUrl: string
  mimeType: string
  category?: string
  source?: FittingRoomOutfitPiece['source']
  notice?: { title: string; galleryItemId: string }
}): Promise<void> {
  const updatedAt = new Date().toISOString()
  const piece: FittingRoomOutfitPiece = {
    id: newOutfitPieceId(),
    // Full Social looks are dresses/one-pieces — not ambiguous auto plates.
    category: opts.category?.trim() || 'dresses',
    dataUrl: opts.dataUrl,
    mimeType: opts.mimeType,
    updatedAt,
    source: opts.source ?? 'fashionrise_look',
    ...(opts.notice?.galleryItemId
      ? { galleryItemId: opts.notice.galleryItemId }
      : {}),
  }
  await writeOutfitSession({
    key: outfitKey(opts.userId),
    userId: opts.userId,
    pieces: [piece],
    updatedAt,
  })
  await writeFittingRoomAsset({
    userId: opts.userId,
    kind: 'garment',
    dataUrl: piece.dataUrl,
    mimeType: piece.mimeType,
    updatedAt,
    garmentCategory: piece.category,
  })
  if (opts.notice && typeof sessionStorage !== 'undefined') {
    const payload: FittingRoomPlantedNotice = {
      title: opts.notice.title,
      galleryItemId: opts.notice.galleryItemId,
      at: updatedAt,
    }
    try {
      sessionStorage.setItem(FITTING_ROOM_PLANTED_NOTICE_KEY, JSON.stringify(payload))
    } catch {
      /* private mode / quota */
    }
  }
}

/** Read + clear one-shot planted notice for Fitting Room UI. */
export function consumeFittingRoomPlantedNotice(): FittingRoomPlantedNotice | null {
  if (typeof sessionStorage === 'undefined') return null
  try {
    const raw = sessionStorage.getItem(FITTING_ROOM_PLANTED_NOTICE_KEY)
    if (!raw) return null
    sessionStorage.removeItem(FITTING_ROOM_PLANTED_NOTICE_KEY)
    const parsed = JSON.parse(raw) as FittingRoomPlantedNotice
    if (!parsed || typeof parsed.galleryItemId !== 'string') return null
    return {
      title: typeof parsed.title === 'string' ? parsed.title : 'Look',
      galleryItemId: parsed.galleryItemId,
      at: typeof parsed.at === 'string' ? parsed.at : new Date().toISOString(),
    }
  } catch {
    return null
  }
}
