import { describe, expect, it } from 'vitest'
import { CONTACT_EMAIL, buildContactMailto } from './contact'

describe('buildContactMailto', () => {
  it('targets the FashionRise support inbox', () => {
    const href = buildContactMailto({
      subject: 'Help with Try On',
      message: 'My preview looks wrong.',
      replyEmail: 'designer@example.com',
      username: 'maya',
    })
    expect(href.startsWith(`mailto:${CONTACT_EMAIL}?`)).toBe(true)
    const query = new URL(href).searchParams
    expect(query.get('subject')).toBe('Help with Try On')
    expect(query.get('body')).toContain('My preview looks wrong.')
    expect(query.get('body')).toContain('Studio user: maya')
    expect(query.get('body')).toContain('Reply to: designer@example.com')
  })

  it('falls back to a default subject when blank', () => {
    const href = buildContactMailto({ subject: '  ', message: 'Hi' })
    const query = new URL(href).searchParams
    expect(query.get('subject')).toBe('FashionRise message')
  })
})
