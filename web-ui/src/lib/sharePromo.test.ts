import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  FASHIONRISE_PUBLIC_URL,
  buildShareCaption,
  buildWhatsAppShareUrl,
  buildInstagramProfileUrl,
} from '@/lib/sharePromo'

describe('sharePromo', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('builds an app invite caption with FashionRise promo + public URL', () => {
    const caption = buildShareCaption({ kind: 'app' })
    expect(caption).toContain('FashionRise')
    expect(caption).toContain('Dream · Sketch · Create')
    expect(caption).toContain(FASHIONRISE_PUBLIC_URL)
    expect(caption).toMatch(/@\w+/)
  })

  it('builds a look caption that includes the look title', () => {
    const caption = buildShareCaption({ kind: 'look', title: 'Silk Wrap Dress' })
    expect(caption).toContain('Silk Wrap Dress')
    expect(caption).toContain(FASHIONRISE_PUBLIC_URL)
  })

  it('builds a WhatsApp deep link with encoded promo text', () => {
    const caption = buildShareCaption({ kind: 'app' })
    const url = buildWhatsAppShareUrl(caption)
    expect(url.startsWith('https://wa.me/?text=')).toBe(true)
    expect(decodeURIComponent(url.split('text=')[1])).toContain('FashionRise')
  })

  it('points Instagram at the configured profile', () => {
    expect(buildInstagramProfileUrl('fashionrise')).toBe(
      'https://www.instagram.com/fashionrise/',
    )
  })
})
