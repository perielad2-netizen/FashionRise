import { describe, expect, it } from 'vitest'
import { isPushDestinationPath, sanitizePushDestination } from './pushDestination'

describe('pushDestination', () => {
  it('allows studio and privacy only', () => {
    expect(isPushDestinationPath('/studio/runway')).toBe(true)
    expect(isPushDestinationPath('/studio/fashionrise')).toBe(true)
    expect(isPushDestinationPath('/privacy')).toBe(true)
    expect(isPushDestinationPath('/reset-password')).toBe(false)
    expect(isPushDestinationPath('/verify-email')).toBe(false)
    expect(isPushDestinationPath('/forgot-password')).toBe(false)
    expect(isPushDestinationPath('/auth/google/complete')).toBe(false)
  })

  it('strips and rejects credential-bearing push URLs', () => {
    expect(sanitizePushDestination('/studio/runway')).toBe('/studio/runway')
    expect(sanitizePushDestination('/studio/fashionrise')).toBe('/studio/fashionrise')
    expect(sanitizePushDestination('https://fashionrise.app/studio/runway')).toBe('/studio/runway')
    expect(sanitizePushDestination('/reset-password#token=abcdefghijklmnopqrstuvwxyz')).toBe(
      '/studio/fashionrise',
    )
    expect(sanitizePushDestination('/verify-email?token=abc')).toBe('/studio/fashionrise')
    expect(sanitizePushDestination('/studio/home?code=oauth')).toBe('/studio/fashionrise')
    expect(sanitizePushDestination('/auth/google/complete')).toBe('/studio/fashionrise')
  })

  it('allows Manage friends deep-link query only', () => {
    expect(sanitizePushDestination('/studio/fashionrise?friends=1')).toBe(
      '/studio/fashionrise?friends=1',
    )
    expect(sanitizePushDestination('https://fashionrise.app/studio/fashionrise?friends=1')).toBe(
      '/studio/fashionrise?friends=1',
    )
    expect(sanitizePushDestination('/studio/fashionrise?friends=1&token=x')).toBe(
      '/studio/fashionrise',
    )
    expect(sanitizePushDestination('/studio/runway?friends=1')).toBe('/studio/runway')
  })
})
