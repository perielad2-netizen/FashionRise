import { afterEach, describe, expect, it, vi } from 'vitest'
import { fileToFittingRoomDataUrl } from './fittingRoomStore'

describe('fileToFittingRoomDataUrl EXIF bake', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('bakes createImageBitmap pixels into an upright JPEG data URL', async () => {
    const close = vi.fn()
    const bitmap = {
      width: 20,
      height: 40,
      close,
    } as unknown as ImageBitmap

    const createImageBitmap = vi.fn(async () => bitmap)
    vi.stubGlobal('createImageBitmap', createImageBitmap)

    const drawImage = vi.fn()
    const fillRect = vi.fn()
    const toDataURL = vi.fn(() => 'data:image/jpeg;base64,abc')
    const getContext = vi.fn(() => ({ drawImage, fillRect, fillStyle: '' }))
    const canvas = { width: 0, height: 0, getContext, toDataURL }
    vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
      if (tag === 'canvas') return canvas as unknown as HTMLCanvasElement
      return document.createElementNS('http://www.w3.org/1999/xhtml', tag) as HTMLElement
    })

    const file = new File([new Uint8Array([1, 2, 3])], 'phone.jpg', { type: 'image/jpeg' })
    const result = await fileToFittingRoomDataUrl(file)

    expect(createImageBitmap).toHaveBeenCalled()
    expect(canvas.width).toBe(20)
    expect(canvas.height).toBe(40)
    expect(fillRect).toHaveBeenCalled()
    expect(drawImage).toHaveBeenCalledWith(bitmap, 0, 0, 20, 40)
    expect(close).toHaveBeenCalled()
    expect(toDataURL).toHaveBeenCalledWith('image/jpeg', expect.any(Number))
    expect(result).toEqual({ dataUrl: 'data:image/jpeg;base64,abc', mimeType: 'image/jpeg' })
  })

  it('rejects non-image files', async () => {
    const file = new File(['x'], 'notes.txt', { type: 'text/plain' })
    await expect(fileToFittingRoomDataUrl(file)).rejects.toThrow(/photo or clothing/i)
  })
})
