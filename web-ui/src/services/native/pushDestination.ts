/**
 * Canonical push notification destination contract (FE).
 *
 * Must stay in lockstep with:
 * - backend/app/services/push_destinations.py
 * - public/push-sw-handlers.js
 *
 * FashionRise Social destinations use stable GalleryItem / comment / friendship
 * UUIDs. Never MagicLook IDs. `?look=` is My Looks only — not a push destination.
 */

export const PUSH_PATH_ALLOWLIST: readonly string[] = ['/studio', '/privacy']

const BLOCKED_PUSH_PATH_PREFIXES: readonly string[] = [
  '/reset-password',
  '/verify-email',
  '/forgot-password',
  '/auth/google',
  '/auth/cf-access',
  '/api/',
]

const TOKENISH =
  /(?:^|[?#&])(?:token|code|access_token|refresh_token|id_token|handoff)=/i

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

const ALLOWED_HOSTS = new Set(['fashionrise.app', 'www.fashionrise.app'])

const FALLBACK = '/studio/fashionrise'

export function isPushDestinationPath(pathname: string): boolean {
  const path = (pathname || '/').split('?')[0].split('#')[0] || '/'
  if (BLOCKED_PUSH_PATH_PREFIXES.some((p) => path === p || path.startsWith(p))) {
    return false
  }
  return PUSH_PATH_ALLOWLIST.some(
    (allowed) => path === allowed || path.startsWith(`${allowed}/`),
  )
}

function isUuid(value: string): boolean {
  return UUID_RE.test((value || '').trim())
}

function sanitizeFashionriseQuery(params: URLSearchParams): string | null {
  const keys = [...params.keys()]
  if (keys.length !== new Set(keys).size) return null
  const allowed = new Set([
    'item',
    'comments',
    'comment',
    'friends',
    'section',
    'friendship',
  ])
  for (const key of keys) {
    if (!allowed.has(key)) return null
  }

  const hasItem = params.has('item')
  const hasFriends = params.has('friends')
  if (hasItem && hasFriends) return null
  if (!hasItem && !hasFriends) return null

  const out = new URLSearchParams()

  if (hasItem) {
    const item = (params.get('item') || '').trim()
    if (!isUuid(item)) return null
    out.set('item', item.toLowerCase())
    const comment = params.get('comment')
    const comments = params.get('comments')
    if (comment != null) {
      const c = comment.trim()
      if (!isUuid(c)) return null
      out.set('comments', '1')
      out.set('comment', c.toLowerCase())
    } else if (comments != null) {
      if (comments.trim() !== '1') return null
      out.set('comments', '1')
    }
    if (params.has('section') || params.has('friendship')) return null
    return out.toString()
  }

  if ((params.get('friends') || '').trim() !== '1') return null
  out.set('friends', '1')
  const section = params.get('section')
  const friendship = params.get('friendship')
  if (section != null) {
    const s = section.trim().toLowerCase()
    if (s !== 'requests' && s !== 'accepted') return null
    out.set('section', s)
  }
  if (friendship != null) {
    const f = friendship.trim()
    if (!isUuid(f)) return null
    out.set('friendship', f.toLowerCase())
  }
  if (params.has('item') || params.has('comments') || params.has('comment')) {
    return null
  }
  return out.toString()
}

/** Safe SPA path for a push tap. Never returns credential-bearing URLs. */
export function sanitizePushDestination(raw: unknown): string {
  if (typeof raw !== 'string' || !raw.trim()) return FALLBACK
  let url = raw.trim()
  try {
    if (/^https?:\/\//i.test(url) || url.startsWith('//')) {
      const u = new URL(url.startsWith('//') ? `https:${url}` : url)
      if (!ALLOWED_HOSTS.has(u.hostname.toLowerCase())) return FALLBACK
      url = `${u.pathname}${u.search}`
    }
  } catch {
    return FALLBACK
  }
  if (!url.startsWith('/') || url.startsWith('//')) return FALLBACK
  if (TOKENISH.test(url)) return FALLBACK
  const path = url.split('?')[0].split('#')[0] || '/'
  if (!isPushDestinationPath(path)) return FALLBACK
  if (path === '/') return FALLBACK

  const query = (url.split('?')[1] || '').split('#')[0]
  if (!query) return path

  if (path === '/studio/fashionrise') {
    const params = new URLSearchParams(query)
    const safe = sanitizeFashionriseQuery(params)
    if (safe == null) return path
    return safe ? `${path}?${safe}` : path
  }

  // Other studio/privacy paths: strip query.
  return path
}

export type ParsedPushDestination =
  | { kind: 'fashionrise' }
  | {
      kind: 'item'
      itemId: string
      openComments: boolean
      commentId: string | null
    }
  | {
      kind: 'friends'
      section: 'requests' | 'accepted' | null
      friendshipId: string | null
    }
  | { kind: 'other'; path: string }

/** Parse a sanitized FashionRise push destination for SPA focus wiring. */
export function parsePushDestination(raw: unknown): ParsedPushDestination {
  const safe = sanitizePushDestination(raw)
  const path = safe.split('?')[0]
  const query = safe.includes('?') ? safe.slice(safe.indexOf('?') + 1) : ''
  if (path !== '/studio/fashionrise') {
    return { kind: 'other', path: safe }
  }
  if (!query) return { kind: 'fashionrise' }
  const params = new URLSearchParams(query)
  if (params.get('friends') === '1') {
    const sectionRaw = params.get('section')
    const section =
      sectionRaw === 'requests' || sectionRaw === 'accepted' ? sectionRaw : null
    return {
      kind: 'friends',
      section,
      friendshipId: params.get('friendship'),
    }
  }
  const itemId = params.get('item')
  if (itemId && isUuid(itemId)) {
    return {
      kind: 'item',
      itemId: itemId.toLowerCase(),
      openComments: params.get('comments') === '1' || Boolean(params.get('comment')),
      commentId: params.get('comment'),
    }
  }
  return { kind: 'fashionrise' }
}
