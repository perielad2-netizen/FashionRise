import { describe, expect, it } from 'vitest'
import {
  isPushDestinationPath,
  parsePushDestination,
  sanitizePushDestination,
} from './pushDestination'

const ITEM = '11111111-1111-4111-8111-111111111111'
const COMMENT = '22222222-2222-4222-8222-222222222222'
const FRIENDSHIP = '33333333-3333-4333-8333-333333333333'

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

  it('allows typed FashionRise Social queries', () => {
    expect(sanitizePushDestination('/studio/fashionrise?friends=1')).toBe(
      '/studio/fashionrise?friends=1',
    )
    expect(
      sanitizePushDestination(
        `https://fashionrise.app/studio/fashionrise?item=${ITEM}&comments=1&comment=${COMMENT}`,
      ),
    ).toBe(`/studio/fashionrise?item=${ITEM}&comments=1&comment=${COMMENT}`)
    expect(
      sanitizePushDestination(
        `/studio/fashionrise?friends=1&section=requests&friendship=${FRIENDSHIP}`,
      ),
    ).toBe(`/studio/fashionrise?friends=1&section=requests&friendship=${FRIENDSHIP}`)
    expect(sanitizePushDestination('/studio/fashionrise?friends=1&token=x')).toBe(
      '/studio/fashionrise',
    )
    expect(sanitizePushDestination('/studio/runway?friends=1')).toBe('/studio/runway')
    expect(sanitizePushDestination(`/studio/fashionrise?item=${ITEM}&friends=1`)).toBe(
      '/studio/fashionrise',
    )
    expect(
      sanitizePushDestination('https://fashionrise.app.evil.example/studio/fashionrise'),
    ).toBe('/studio/fashionrise')
  })

  it('parses destinations for SPA focus', () => {
    expect(parsePushDestination(`/studio/fashionrise?item=${ITEM}&comments=1&comment=${COMMENT}`)).toEqual(
      {
        kind: 'item',
        itemId: ITEM,
        openComments: true,
        commentId: COMMENT,
      },
    )
    expect(
      parsePushDestination(
        `/studio/fashionrise?friends=1&section=accepted&friendship=${FRIENDSHIP}`,
      ),
    ).toEqual({
      kind: 'friends',
      section: 'accepted',
      friendshipId: FRIENDSHIP,
    })
  })
})
