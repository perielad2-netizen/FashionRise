/* FashionRise Web Push handlers — imported by the generated Workbox SW.
 * Keep this file free of HTML navigation fallbacks (CF Access SW safety).
 * Push destinations never include password-reset, verification, or OAuth tokens.
 * Destination contract must match pushDestination.ts + backend push_destinations.py.
 */
/* eslint-disable no-restricted-globals */

const PUSH_PATH_ALLOWLIST = ['/studio', '/privacy']
const BLOCKED_PUSH_PREFIXES = [
  '/reset-password',
  '/verify-email',
  '/forgot-password',
  '/auth/google',
  '/auth/cf-access',
  '/api/',
]
const TOKENISH = /(?:^|[?#&])(?:token|code|access_token|refresh_token|id_token|handoff)=/i
const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
const ALLOWED_HOSTS = new Set(['fashionrise.app', 'www.fashionrise.app'])
const FALLBACK = '/studio/fashionrise'

function isUuid(value) {
  return UUID_RE.test(String(value || '').trim())
}

function pathAllowed(path) {
  if (BLOCKED_PUSH_PREFIXES.some((p) => path === p || path.startsWith(p))) return false
  if (path === '/') return false
  return PUSH_PATH_ALLOWLIST.some((p) => path === p || path.startsWith(`${p}/`))
}

function sanitizeFashionriseQuery(params) {
  const keys = []
  params.forEach((_, key) => keys.push(key))
  if (keys.length !== new Set(keys).size) return null
  const allowed = new Set(['item', 'comments', 'comment', 'friends', 'section', 'friendship'])
  for (const key of keys) {
    if (!allowed.has(key)) return null
  }
  const hasItem = params.has('item')
  const hasFriends = params.has('friends')
  if (hasItem && hasFriends) return null
  if (!hasItem && !hasFriends) return null
  const out = new URLSearchParams()
  if (hasItem) {
    const item = String(params.get('item') || '').trim()
    if (!isUuid(item)) return null
    out.set('item', item.toLowerCase())
    const comment = params.get('comment')
    const comments = params.get('comments')
    if (comment != null) {
      const c = String(comment).trim()
      if (!isUuid(c)) return null
      out.set('comments', '1')
      out.set('comment', c.toLowerCase())
    } else if (comments != null) {
      if (String(comments).trim() !== '1') return null
      out.set('comments', '1')
    }
    if (params.has('section') || params.has('friendship')) return null
    return out.toString()
  }
  if (String(params.get('friends') || '').trim() !== '1') return null
  out.set('friends', '1')
  const section = params.get('section')
  const friendship = params.get('friendship')
  if (section != null) {
    const s = String(section).trim().toLowerCase()
    if (s !== 'requests' && s !== 'accepted') return null
    out.set('section', s)
  }
  if (friendship != null) {
    const f = String(friendship).trim()
    if (!isUuid(f)) return null
    out.set('friendship', f.toLowerCase())
  }
  if (params.has('item') || params.has('comments') || params.has('comment')) return null
  return out.toString()
}

function sanitizePushUrl(raw) {
  let url = typeof raw === 'string' && raw.trim() ? raw.trim() : FALLBACK
  try {
    if (/^https?:\/\//i.test(url) || url.startsWith('//')) {
      const u = new URL(url.startsWith('//') ? `https:${url}` : url)
      if (!ALLOWED_HOSTS.has(String(u.hostname || '').toLowerCase())) return FALLBACK
      url = `${u.pathname}${u.search}`
    }
  } catch {
    return FALLBACK
  }
  if (!url.startsWith('/') || url.startsWith('//')) return FALLBACK
  if (TOKENISH.test(url)) return FALLBACK
  const path = url.split('?')[0].split('#')[0] || '/'
  if (!pathAllowed(path)) return FALLBACK
  const query = (url.split('?')[1] || '').split('#')[0]
  if (!query) return path
  if (path === '/studio/fashionrise') {
    const safe = sanitizeFashionriseQuery(new URLSearchParams(query))
    if (safe == null) return path
    return safe ? `${path}?${safe}` : path
  }
  return path
}

self.addEventListener('push', (event) => {
  let data = {
    title: 'FashionRise',
    body: 'Something new on FashionRise',
    url: FALLBACK,
    tag: 'fashionrise-social',
  }
  try {
    if (event.data) {
      const parsed = event.data.json()
      data = { ...data, ...parsed }
    }
  } catch {
    try {
      const text = event.data && event.data.text()
      if (text) data.body = text
    } catch {
      /* keep defaults */
    }
  }
  const safeUrl = sanitizePushUrl(data.url)
  event.waitUntil(
    self.registration.showNotification(data.title || 'FashionRise', {
      body: data.body || '',
      tag: data.tag || 'fashionrise-social',
      data: { url: safeUrl },
      icon: '/icons/icon-192.png',
      badge: '/icons/icon-192.png',
    }),
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const target = sanitizePushUrl(
    (event.notification && event.notification.data && event.notification.data.url) ||
      FALLBACK,
  )
  event.waitUntil(
    (async () => {
      const all = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      for (const client of all) {
        if ('focus' in client) {
          await client.focus()
          if ('navigate' in client) {
            try {
              await client.navigate(target)
              return
            } catch {
              /* older browsers — fall through to openWindow */
            }
          }
        }
      }
      if (self.clients.openWindow) {
        await self.clients.openWindow(target)
      }
    })(),
  )
})
