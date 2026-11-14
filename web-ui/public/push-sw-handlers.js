/* FashionRise Web Push handlers — imported by the generated Workbox SW.
 * Keep this file free of HTML navigation fallbacks (CF Access SW safety).
 * Push destinations never include password-reset, verification, or OAuth tokens.
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

function sanitizePushUrl(raw) {
  const fallback = '/studio/runway'
  let url = typeof raw === 'string' && raw.trim() ? raw.trim() : fallback
  try {
    if (/^https?:\/\//i.test(url)) {
      const u = new URL(url)
      if (u.hostname !== 'fashionrise.app' && u.hostname !== 'www.fashionrise.app') {
        return fallback
      }
      url = `${u.pathname}${u.search}${u.hash}`
    }
  } catch {
    return fallback
  }
  if (!url.startsWith('/') || url.startsWith('//')) return fallback
  if (TOKENISH.test(url)) return fallback
  const path = url.split('?')[0].split('#')[0] || '/'
  if (BLOCKED_PUSH_PREFIXES.some((p) => path === p || path.startsWith(p))) return fallback
  const ok = PUSH_PATH_ALLOWLIST.some((p) => path === p || path.startsWith(`${p}/`))
  return ok && path !== '/' ? path : fallback
}

self.addEventListener('push', (event) => {
  let data = {
    title: 'FashionRise',
    body: 'Something new on Runway',
    url: '/studio/runway',
    tag: 'fashionrise-runway',
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
      tag: data.tag || 'fashionrise-runway',
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
      '/studio/runway',
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
            } catch {
              /* older browsers */
            }
          }
          return
        }
      }
      if (self.clients.openWindow) {
        await self.clients.openWindow(target)
      }
    })(),
  )
})
