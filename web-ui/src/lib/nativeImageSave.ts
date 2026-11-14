/**
 * Capacitor-backed image save for native shells.
 * Never uses WebView `<a download>` (no-op on Android/iOS WebViews).
 */

export class SaveCancelledError extends Error {
  readonly name = 'SaveCancelledError'
  constructor(message = 'Download cancelled') {
    super(message)
  }
}

export type NativeImageSaveDeps = {
  platform?: () => 'ios' | 'android' | 'web'
  writeCacheFile?: (path: string, base64: string) => Promise<{ uri: string }>
  ensureAlbumId?: (albumName: string) => Promise<string | undefined>
  savePhoto?: (opts: {
    path: string
    albumIdentifier?: string
    fileName: string
  }) => Promise<unknown>
  shareFiles?: (opts: { title: string; files: string[]; dialogTitle?: string }) => Promise<unknown>
}

const ALBUM_NAME = 'FashionRise'

export async function blobToBase64(blob: Blob): Promise<string> {
  const buffer = await blob.arrayBuffer()
  const bytes = new Uint8Array(buffer)
  const chunk = 0x8000
  let binary = ''
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk))
  }
  return btoa(binary)
}

function isUserCancel(err: unknown): boolean {
  if (!err || typeof err !== 'object') return false
  const name = 'name' in err ? String((err as { name: unknown }).name) : ''
  const message = 'message' in err ? String((err as { message: unknown }).message) : ''
  if (name === 'AbortError' || name === 'SaveCancelledError') return true
  // Capacitor Share / Android activity cancel variants
  if (/cancel/i.test(message) || /dismiss/i.test(message)) return true
  return false
}

async function defaultWriteCacheFile(path: string, base64: string): Promise<{ uri: string }> {
  const { Filesystem, Directory } = await import('@capacitor/filesystem')
  const result = await Filesystem.writeFile({
    path,
    data: base64,
    directory: Directory.Cache,
  })
  return { uri: result.uri }
}

async function defaultEnsureAlbumId(albumName: string): Promise<string | undefined> {
  const { Media } = await import('@capacitor-community/media')
  const { Capacitor } = await import('@capacitor/core')

  let { albums } = await Media.getAlbums()
  let found = albums.find((a) => a.name === albumName)
  if (!found) {
    await Media.createAlbum({ name: albumName })
    ;({ albums } = await Media.getAlbums())
    found = albums.find((a) => a.name === albumName)
  }

  if (Capacitor.getPlatform() === 'android') {
    try {
      const { path } = await Media.getAlbumsPath()
      const scoped = albums.find((a) => a.name === albumName && a.identifier.startsWith(path))
      if (scoped) return scoped.identifier
    } catch {
      /* getAlbumsPath optional on some devices */
    }
  }

  return found?.identifier
}

async function defaultSavePhoto(opts: {
  path: string
  albumIdentifier?: string
  fileName: string
}): Promise<unknown> {
  const { Media } = await import('@capacitor-community/media')
  return Media.savePhoto(opts)
}

async function defaultShareFiles(opts: {
  title: string
  files: string[]
  dialogTitle?: string
}): Promise<unknown> {
  const { Share } = await import('@capacitor/share')
  return Share.share(opts)
}

/**
 * Save an image blob to a user-accessible place on native.
 * Primary: Photos/Gallery via @capacitor-community/media.
 * Fallback: OS share sheet with a real file:// URI (@capacitor/share).
 */
export async function saveImageBlobNative(
  blob: Blob,
  filename: string,
  deps: NativeImageSaveDeps = {},
): Promise<'gallery' | 'share'> {
  const safeName =
    filename.replace(/[^\w.\-]+/g, '-').replace(/^-|-$/g, '') || 'fashionrise-look.png'
  let plat: 'ios' | 'android' | 'web'
  if (deps.platform) {
    plat = deps.platform()
  } else {
    try {
      const { Capacitor } = await import('@capacitor/core')
      const p = Capacitor.getPlatform()
      plat = p === 'ios' || p === 'android' ? p : 'web'
    } catch {
      plat = 'web'
    }
  }
  if (plat === 'web') {
    throw new Error('Native image save is only available in the iOS/Android app')
  }

  const base64 = await blobToBase64(blob)
  const cachePath = `fr-dl/${Date.now()}-${safeName}`
  const write = deps.writeCacheFile ?? defaultWriteCacheFile
  const { uri } = await write(cachePath, base64)
  if (!uri) throw new Error('Could not write the image to device storage')

  const fileNameNoExt = safeName.replace(/\.[^.]+$/, '') || 'fashionrise-look'
  const ensureAlbum = deps.ensureAlbumId ?? defaultEnsureAlbumId
  const savePhoto = deps.savePhoto ?? defaultSavePhoto

  try {
    const albumIdentifier = await ensureAlbum(ALBUM_NAME)
    if (plat === 'android' && !albumIdentifier) {
      throw new Error('Could not open the FashionRise photo album')
    }
    await savePhoto({
      path: uri,
      albumIdentifier,
      fileName: fileNameNoExt,
    })
    return 'gallery'
  } catch (galleryErr) {
    if (isUserCancel(galleryErr)) throw new SaveCancelledError()

    // Gallery write failed — offer a real file via the system share sheet.
    const shareFiles = deps.shareFiles ?? defaultShareFiles
    try {
      await shareFiles({
        title: safeName,
        files: [uri],
        dialogTitle: 'Save image',
      })
      return 'share'
    } catch (shareErr) {
      if (isUserCancel(shareErr)) throw new SaveCancelledError()
      const galleryMsg =
        galleryErr instanceof Error && galleryErr.message.trim()
          ? galleryErr.message
          : 'Could not save to Photos'
      throw new Error(
        shareErr instanceof Error && shareErr.message.trim()
          ? shareErr.message
          : galleryMsg,
      )
    }
  }
}
