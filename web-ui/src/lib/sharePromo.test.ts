import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const platform = vi.hoisted(() => ({
  isNativeShell: vi.fn(() => false),
}))

vi.mock('@/services/native/platform', () => ({
  isNativeShell: () => platform.isNativeShell(),
  nativePlatform: () => (platform.isNativeShell() ? 'android' : 'web'),
  isNativeBuild: () => false,
}))

const capacitorShare = vi.hoisted(() => ({
  share: vi.fn().mockResolvedValue({}),
}))

vi.mock('@capacitor/share', () => ({
  Share: {
    share: (...args: unknown[]) => capacitorShare.share(...args),
  },
}))

vi.mock('@capacitor/core', () => ({
  Capacitor: {
    isNativePlatform: () => platform.isNativeShell(),
    getPlatform: () => (platform.isNativeShell() ? 'android' : 'web'),
  },
}))

vi.mock('@/lib/nativeImageSave', () => ({
  blobToBase64: vi.fn(async () => 'YWJj'),
  writeCacheFileForDownload: vi.fn(async () => ({
    uri: 'file:///cache/fr-share/look.png',
  })),
}))

import {
  FASHIONRISE_PUBLIC_URL,
  buildShareCaption,
  buildWhatsAppShareUrl,
  canUseNativeShare,
  requestShare,
} from '@/lib/sharePromo'

describe('sharePromo', () => {
  beforeEach(() => {
    platform.isNativeShell.mockReturnValue(false)
    capacitorShare.share.mockClear()
    capacitorShare.share.mockResolvedValue({})
  })

  afterEach(() => {
    vi.restoreAllMocks()
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    delete (navigator as any).share
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    delete (navigator as any).canShare
  })

  it('builds a store-aligned FashionRise caption with a single site URL', () => {
    const caption = buildShareCaption({ kind: 'look' })
    expect(caption).toContain('Created with FashionRise')
    expect(caption).toContain('AI fashion studio: sketch, Magic looks, models, try-on, fabrics & tech packs.')
    expect(caption).toContain(FASHIONRISE_PUBLIC_URL)
    expect(caption).not.toContain('Search Google for FashionRise')
    expect(caption.split(FASHIONRISE_PUBLIC_URL).length - 1).toBe(1)
  })

  it('omits the look title from the public caption', () => {
    const caption = buildShareCaption({ kind: 'look', title: 'Silk Wrap Dress' })
    expect(caption).not.toContain('Silk Wrap Dress')
    expect(caption.startsWith('Created with FashionRise')).toBe(true)
    expect(caption.split('\n')).toEqual([
      'Created with FashionRise',
      'AI fashion studio: sketch, Magic looks, models, try-on, fabrics & tech packs.',
      FASHIONRISE_PUBLIC_URL,
    ])
  })

  it('builds a WhatsApp deep link with the attribution caption', () => {
    const caption = buildShareCaption({ kind: 'look' })
    const url = buildWhatsAppShareUrl(caption)
    expect(url.startsWith('https://wa.me/?text=')).toBe(true)
    expect(decodeURIComponent(url.split('text=')[1])).toContain('Created with FashionRise')
  })

  it('requestShare opens the OS share sheet when Web Share is available', async () => {
    const share = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { share, canShare: undefined })
    const result = await requestShare({ kind: 'look', title: 'Gown' })
    expect(result).toBe('shared')
    expect(share).toHaveBeenCalledTimes(1)
    const data = share.mock.calls[0][0] as ShareData
    expect(data.text).toContain('Created with FashionRise')
    expect(data.text).toContain('AI fashion studio')
    expect(data.url).toBeUndefined()
  })

  it('requestShare asks for fallback when Web Share is missing on web', async () => {
    const result = await requestShare({ kind: 'look' })
    expect(result).toBe('needs-fallback')
  })

  it('requestShare uses Capacitor Share on native Android (no custom popup)', async () => {
    platform.isNativeShell.mockReturnValue(true)
    expect(canUseNativeShare()).toBe(true)

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      blob: async () => new Blob(['png'], { type: 'image/png' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await requestShare({
      kind: 'look',
      title: 'Wings',
      imageUrl: 'blob:look',
      imageFileName: 'fashionrise-look.png',
    })

    expect(result).toBe('shared')
    expect(capacitorShare.share).toHaveBeenCalledTimes(1)
    const args = capacitorShare.share.mock.calls[0][0] as {
      text: string
      files?: string[]
      dialogTitle?: string
    }
    expect(args.text).toContain('Created with FashionRise')
    expect(args.text).toContain('AI fashion studio')
    expect(args.text).toContain(FASHIONRISE_PUBLIC_URL)
    expect((args as { url?: string }).url).toBeUndefined()
    expect(args.files?.[0]).toContain('file://')
    expect(args.dialogTitle).toMatch(/Share your look/i)
  })

  it('Capacitor Share cancel does not open the fallback sheet', async () => {
    platform.isNativeShell.mockReturnValue(true)
    capacitorShare.share.mockRejectedValueOnce(new Error('Share cancelled'))
    const result = await requestShare({ kind: 'look' })
    expect(result).toBe('cancelled')
  })
})
