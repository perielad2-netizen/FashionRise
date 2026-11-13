import { describe, expect, it } from 'vitest'
import { parseAndroidGoogleHandoffUrl } from './googleOAuthReturn'

describe('parseAndroidGoogleHandoffUrl', () => {
  it('parses custom-scheme handoff without requiring tokens in the URL', () => {
    const code = 'abcdefghijklmnopqrstuvwxyz012345'
    const url = `app.fashionrise.studio://auth/google/native?code=${code}&next=%2Fstudio%2Fhome`
    expect(parseAndroidGoogleHandoffUrl(url)).toEqual({
      code,
      next: '/studio/home',
    })
  })

  it('rejects non-FashionRise schemes and missing codes', () => {
    expect(parseAndroidGoogleHandoffUrl('https://fashionrise.app/auth/google/complete')).toBeNull()
    expect(parseAndroidGoogleHandoffUrl('app.fashionrise.studio://auth/google/native')).toBeNull()
    expect(
      parseAndroidGoogleHandoffUrl('app.fashionrise.studio://auth/google/native?code=short'),
    ).toBeNull()
  })

  it('sanitizes unsafe next paths', () => {
    const code = 'abcdefghijklmnopqrstuvwxyz012345'
    const url = `app.fashionrise.studio://auth/google/native?code=${code}&next=https://evil.example`
    expect(parseAndroidGoogleHandoffUrl(url)?.next).toBe('/studio/home')
  })
})
