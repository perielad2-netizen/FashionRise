import { describe, expect, it } from 'vitest'
import {
  FASHIONRISE_PUBLIC_URL,
  buildFacebookShareUrl,
  buildShareCaption,
  buildWhatsAppShareUrl,
} from '@/lib/sharePromo'

describe('sharePromo', () => {
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

  it('builds a Facebook sharer URL for the FashionRise app page', () => {
    expect(buildFacebookShareUrl()).toContain('facebook.com/sharer')
    expect(buildFacebookShareUrl()).toContain(encodeURIComponent(FASHIONRISE_PUBLIC_URL))
  })
})
