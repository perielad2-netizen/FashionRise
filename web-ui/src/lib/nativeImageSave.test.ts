import { describe, expect, it, vi } from 'vitest'
import { blobToBase64, SaveCancelledError, saveImageBlobNative } from './nativeImageSave'

describe('nativeImageSave', () => {
  it('encodes blobs to base64 without corruption', async () => {
    const bytes = new Uint8Array([1, 2, 3, 250, 255])
    const b64 = await blobToBase64(new Blob([bytes], { type: 'image/png' }))
    expect(b64).toBe(btoa(String.fromCharCode(...bytes)))
  })

  it('saves to gallery via Media when album is available', async () => {
    const writeCacheFile = vi.fn(async () => ({ uri: 'file:///cache/look.png' }))
    const ensureAlbumId = vi.fn(async () => 'album-1')
    const savePhoto = vi.fn(async () => ({ identifier: 'photo-1' }))
    const shareFiles = vi.fn()

    const method = await saveImageBlobNative(
      new Blob([new Uint8Array([9, 9])], { type: 'image/png' }),
      'Blush gown-front.png',
      {
        platform: () => 'android',
        writeCacheFile,
        ensureAlbumId,
        savePhoto,
        shareFiles,
      },
    )

    expect(method).toBe('gallery')
    expect(writeCacheFile).toHaveBeenCalled()
    expect(savePhoto).toHaveBeenCalledWith(
      expect.objectContaining({
        path: 'file:///cache/look.png',
        albumIdentifier: 'album-1',
        fileName: 'Blush-gown-front',
      }),
    )
    expect(shareFiles).not.toHaveBeenCalled()
  })

  it('falls back to Capacitor Share when gallery save fails', async () => {
    const shareFiles = vi.fn(async () => undefined)
    const method = await saveImageBlobNative(new Blob(['x'], { type: 'image/png' }), 'look-back.png', {
      platform: () => 'ios',
      writeCacheFile: async () => ({ uri: 'file:///tmp/look.png' }),
      ensureAlbumId: async () => 'album',
      savePhoto: async () => {
        throw new Error('permission denied')
      },
      shareFiles,
    })
    expect(method).toBe('share')
    expect(shareFiles).toHaveBeenCalledWith(
      expect.objectContaining({ files: ['file:///tmp/look.png'] }),
    )
  })

  it('throws SaveCancelledError when the user cancels the share sheet', async () => {
    await expect(
      saveImageBlobNative(new Blob(['x'], { type: 'image/png' }), 'look.png', {
        platform: () => 'android',
        writeCacheFile: async () => ({ uri: 'file:///tmp/x.png' }),
        ensureAlbumId: async () => undefined,
        savePhoto: async () => {
          throw new Error('album missing')
        },
        shareFiles: async () => {
          throw new DOMException('Share canceled', 'AbortError')
        },
      }),
    ).rejects.toBeInstanceOf(SaveCancelledError)
  })

  it('never claims success when both gallery and share fail', async () => {
    await expect(
      saveImageBlobNative(new Blob(['x'], { type: 'image/png' }), 'look.png', {
        platform: () => 'android',
        writeCacheFile: async () => ({ uri: 'file:///tmp/x.png' }),
        ensureAlbumId: async () => 'a',
        savePhoto: async () => {
          throw new Error('gallery boom')
        },
        shareFiles: async () => {
          throw new Error('share boom')
        },
      }),
    ).rejects.toThrow(/share boom|gallery boom/)
  })
})
