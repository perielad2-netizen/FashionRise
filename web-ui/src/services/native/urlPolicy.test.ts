import { describe, expect, it } from 'vitest'
import { classifyFashionRiseUrl, isAllowedInAppPath } from './urlPolicy'

describe('urlPolicy', () => {
  it('allowlists studio and auth SPA paths', () => {
    expect(isAllowedInAppPath('/studio/runway')).toBe(true)
    expect(isAllowedInAppPath('/reset-password')).toBe(true)
    expect(isAllowedInAppPath('/verify-email')).toBe(true)
    expect(isAllowedInAppPath('/privacy')).toBe(true)
    expect(isAllowedInAppPath('/api/v1/auth/login')).toBe(false)
    expect(isAllowedInAppPath('/evil')).toBe(false)
  })

  it('maps fashionrise.app https URLs to in-app paths and keeps hash tokens', () => {
    const c = classifyFashionRiseUrl(
      'https://fashionrise.app/reset-password#token=abcdefghijklmnopqrstuvwxyz012345',
    )
    expect(c.kind).toBe('in_app')
    if (c.kind === 'in_app') {
      expect(c.path).toBe('/reset-password#token=abcdefghijklmnopqrstuvwxyz012345')
    }
  })

  it('rejects api paths on fashionrise.app', () => {
    const c = classifyFashionRiseUrl('https://fashionrise.app/api/v1/auth/me')
    expect(c).toEqual({ kind: 'reject', reason: 'api_path_not_spa' })
  })

  it('classifies Android Google OAuth handoff scheme', () => {
    const c = classifyFashionRiseUrl(
      'app.fashionrise.studio://auth/google/native?code=abcdefghijklmnopqrstuvwxyz',
    )
    expect(c.kind).toBe('oauth_handoff')
  })

  it('allows mailto and WhatsApp as intentional external', () => {
    expect(classifyFashionRiseUrl('mailto:support@fashionrise.app').kind).toBe('external_ok')
    expect(classifyFashionRiseUrl('https://wa.me/123?text=hi').kind).toBe('external_ok')
  })

  it('rejects unknown custom-scheme paths', () => {
    const c = classifyFashionRiseUrl('app.fashionrise.studio://evil/path')
    expect(c.kind).toBe('reject')
  })
})
