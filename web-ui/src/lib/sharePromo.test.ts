import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  FASHIONRISE_PUBLIC_URL,
  buildShareCaption,
  buildWhatsAppShareUrl,
  requestShare,
} from '@/lib/sharePromo'

describe('sharePromo', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    delete (navigator as any).share
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    delete (navigator as any).canShare
  })

  it('builds a Created with FashionRise caption that points people to Google search', () => {
    const caption = buildShareCaption({ kind: 'look' })
    expect(caption).toContain('Created with FashionRise')
    expect(caption).toContain('Search Google for FashionRise')
    expect(caption).toContain(FASHIONRISE_PUBLIC_URL)
  })

  it('includes the look title when provided', () => {
    const caption = buildShareCaption({ kind: 'look', title: 'Silk Wrap Dress' })
    expect(caption).toContain('Silk Wrap Dress')
    expect(caption.startsWith('Created with FashionRise')).toBe(true)
  })

  it('builds a WhatsApp deep link with the attribution caption', () => {
    const caption = buildShareCaption({ kind: 'look' })
    const url = buildWhatsAppShareUrl(caption)
    expect(url.startsWith('https://wa.me/?text=')).toBe(true)
    expect(decodeURIComponent(url.split('text=')[1])).toContain('Created with FashionRise')
  })

  it('requestShare opens the OS share sheet when available', async () => {
    const share = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { share, canShare: undefined })
    const result = await requestShare({ kind: 'look', title: 'Gown' })
    expect(result).toBe('shared')
    expect(share).toHaveBeenCalledTimes(1)
    const data = share.mock.calls[0][0] as ShareData
    expect(data.text).toContain('Created with FashionRise')
    expect(data.text).toContain('Search Google for FashionRise')
  })

  it('requestShare asks for fallback when Web Share is missing', async () => {
    const result = await requestShare({ kind: 'look' })
    expect(result).toBe('needs-fallback')
  })
})
