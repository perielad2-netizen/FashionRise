import { describe, expect, it } from 'vitest'
import {
  APP_STORE_LISTING_URL,
  FASHIONRISE_ASC_APPLE_ID,
  getAppStoreListingUrl,
  isGooglePlayListingPublic,
  MOBILE_STORE_LINKS,
} from './mobileStoreLinks'

describe('mobileStoreLinks', () => {
  it('exposes the verified ASC Apple ID and App Store listing URL', () => {
    expect(FASHIONRISE_ASC_APPLE_ID).toBe('6832116469')
    expect(APP_STORE_LISTING_URL).toBe('https://apps.apple.com/app/id6832116469')
    expect(getAppStoreListingUrl()).toBe(APP_STORE_LISTING_URL)
  })

  it('keeps Google Play as coming soon without a public listing href', () => {
    const play = MOBILE_STORE_LINKS.find((s) => s.id === 'google_play')
    expect(play?.availability).toBe('coming_soon')
    expect(play?.href).toBeNull()
    expect(isGooglePlayListingPublic()).toBe(false)
  })

  it('marks App Store available with a verified href', () => {
    const apple = MOBILE_STORE_LINKS.find((s) => s.id === 'app_store')
    expect(apple?.availability).toBe('available')
    expect(apple?.href).toBe(APP_STORE_LISTING_URL)
  })
})
