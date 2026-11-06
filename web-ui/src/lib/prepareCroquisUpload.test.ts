import { describe, expect, it, vi } from 'vitest'
import {
  CROQUIS_UPLOAD_SOFT_MAX_BYTES,
  prepareCroquisUpload,
} from './prepareCroquisUpload'

describe('prepareCroquisUpload', () => {
  it('passes through tiny files unchanged', async () => {
    const file = new File([new Uint8Array([1, 2, 3])], 'pose.png', { type: 'image/png' })
    const out = await prepareCroquisUpload(file)
    expect(out).toBe(file)
  })

  it('compresses oversized images under the soft max', async () => {
    // Fake a large "file" whose Image decode yields a big canvas.
    const huge = new Uint8Array(12 * 1024 * 1024)
    const file = new File([huge], 'phone-camera.jpg', { type: 'image/jpeg' })

    class FakeImage {
      width = 4000
      height = 3000
      naturalWidth = 4000
      naturalHeight = 3000
      onload: (() => void) | null = null
      onerror: (() => void) | null = null
      set src(_v: string) {
        queueMicrotask(() => this.onload?.())
      }
    }
    vi.stubGlobal('Image', FakeImage as unknown as typeof Image)
    vi.stubGlobal('URL', {
      createObjectURL: () => 'blob:fake',
      revokeObjectURL: () => undefined,
    })

    const originalCreateElement = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
      if (tag !== 'canvas') return originalCreateElement(tag)
      const canvas = originalCreateElement('canvas') as HTMLCanvasElement
      Object.defineProperty(canvas, 'width', { writable: true, value: 0 })
      Object.defineProperty(canvas, 'height', { writable: true, value: 0 })
      canvas.getContext = (() =>
        ({
          drawImage: () => undefined,
        }) as unknown as CanvasRenderingContext2D) as typeof canvas.getContext
      canvas.toBlob = ((cb: BlobCallback, _type?: string, _q?: number) => {
        // ~500KB JPEG stand-in
        cb(new Blob([new Uint8Array(500 * 1024)], { type: 'image/jpeg' }))
      }) as typeof canvas.toBlob
      return canvas
    })

    const out = await prepareCroquisUpload(file)
    expect(out).not.toBe(file)
    expect(out.type).toBe('image/jpeg')
    expect(out.name.endsWith('.jpg')).toBe(true)
    expect(out.size).toBeLessThanOrEqual(CROQUIS_UPLOAD_SOFT_MAX_BYTES)
    expect(out.size).toBe(500 * 1024)

    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })
})
