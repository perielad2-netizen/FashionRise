/**
 * Public mobile-store listing links for browser/PWA Stars purchase guidance.
 *
 * Keep availability easy to flip when Play goes public — do not invent URLs.
 * Native iOS/Android purchasing does not read this module.
 */

/** ASC Apple ID documented in `docs/STORE-DEPLOY.md` / `codemagic.yaml`. */
export const FASHIONRISE_ASC_APPLE_ID = '6832116469'

/**
 * Verified public App Store listing (HTTP 200 after Apple's locale redirect).
 * Canonical id form: https://apps.apple.com/app/id6832116469
 */
export const APP_STORE_LISTING_URL =
  'https://apps.apple.com/app/id6832116469' as const

export type MobileStoreAvailability = 'available' | 'coming_soon'

export type MobileStoreLink = {
  id: 'app_store' | 'google_play'
  title: string
  subtitle: string
  availability: MobileStoreAvailability
  /** Only set when a verified public listing URL exists. */
  href: string | null
}

/**
 * Central store-availability table for the web Stars “Get more Stars” panel.
 * Flip Google Play to `available` and set `href` only after a verified public listing exists.
 */
export const MOBILE_STORE_LINKS: readonly MobileStoreLink[] = [
  {
    id: 'app_store',
    title: 'Apple App Store',
    subtitle: 'Available on iPhone and iPad.',
    availability: 'available',
    href: APP_STORE_LISTING_URL,
  },
  {
    id: 'google_play',
    title: 'Google Play',
    subtitle: 'Coming soon.',
    availability: 'coming_soon',
    href: null,
  },
] as const

export function getAppStoreListingUrl(): string | null {
  const apple = MOBILE_STORE_LINKS.find((s) => s.id === 'app_store')
  return apple?.availability === 'available' && apple.href ? apple.href : null
}

export function isGooglePlayListingPublic(): boolean {
  const play = MOBILE_STORE_LINKS.find((s) => s.id === 'google_play')
  return Boolean(play?.availability === 'available' && play.href)
}
