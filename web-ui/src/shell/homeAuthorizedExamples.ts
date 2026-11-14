/**
 * V2-0031 — Home before/after product examples.
 *
 * Only pairs with explicit PM authorization for home marketing may appear here.
 * Never pull private My Designs / My Looks / Runway content into this catalog.
 * An empty list means the Home gallery UI stays hidden (no fabricated results).
 */

export type HomeExampleImage = {
  /** Public path under `web-ui/public/` or other approved static URL. */
  src: string
  alt: string
  /** Intrinsic pixel size — required so layout reserves space (no CLS). */
  width: number
  height: number
}

export type HomeExampleAuthorization = {
  /** Human-readable provenance (ticket, email, asset pack id). */
  source: string
  /** Must remain home-marketing; other scopes are rejected. */
  licensedFor: 'home-marketing'
  notes?: string
}

export type AuthorizedHomeExample = {
  id: string
  title: string
  authorization: HomeExampleAuthorization
  /**
   * Preferred: one beautiful sketch→AI look composite for the Home hero.
   * When present, the gallery renders this alone (not a two-up cut).
   */
  composite?: HomeExampleImage
  before: HomeExampleImage
  after: HomeExampleImage
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

function isPositiveInt(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value > 0
}

function isHomeExampleImage(value: unknown): value is HomeExampleImage {
  if (!value || typeof value !== 'object') return false
  const img = value as HomeExampleImage
  return (
    isNonEmptyString(img.src) &&
    isNonEmptyString(img.alt) &&
    isPositiveInt(img.width) &&
    isPositiveInt(img.height)
  )
}

/** Runtime guard used by tests and any future catalog loaders. */
export function isAuthorizedHomeExample(value: unknown): value is AuthorizedHomeExample {
  if (!value || typeof value !== 'object') return false
  const row = value as AuthorizedHomeExample
  const auth = row.authorization
  const compositeOk = row.composite === undefined || isHomeExampleImage(row.composite)
  return (
    isNonEmptyString(row.id) &&
    isNonEmptyString(row.title) &&
    !!auth &&
    typeof auth === 'object' &&
    isNonEmptyString(auth.source) &&
    auth.licensedFor === 'home-marketing' &&
    compositeOk &&
    isHomeExampleImage(row.before) &&
    isHomeExampleImage(row.after)
  )
}

/**
 * Production catalog — PM-authorized home marketing pairs only.
 * Source: owner Android QA home-hero example (2026-11-14), single composite preferred.
 */
export const AUTHORIZED_HOME_EXAMPLES: readonly AuthorizedHomeExample[] = Object.freeze([
  {
    id: 'pink-gown-sketch-to-look',
    title: 'Sketch to AI look',
    authorization: {
      source: 'PM Android QA home hero example 2026-11-14 (Addition 01)',
      licensedFor: 'home-marketing',
      notes: 'Owner-provided marketing composite for Home main-idea hero',
    },
    composite: {
      src: '/assets/ui/home/hero-pair-01.jpg',
      alt: 'One FashionRise hero: fashion sketch transforming into an AI look of a pink evening gown',
      width: 838,
      height: 496,
    },
    before: {
      src: '/assets/ui/home/hero-sketch-01.jpg',
      alt: 'Fashion sketch of a strapless pink evening gown',
      width: 403,
      height: 496,
    },
    after: {
      src: '/assets/ui/home/hero-look-01.jpg',
      alt: 'AI fashion look of the same pink evening gown on a model',
      width: 403,
      height: 496,
    },
  },
])

/** Safe accessor — drops any row that fails authorization validation. */
export function getAuthorizedHomeExamples(
  catalog: readonly AuthorizedHomeExample[] = AUTHORIZED_HOME_EXAMPLES,
): readonly AuthorizedHomeExample[] {
  return catalog.filter(isAuthorizedHomeExample)
}
