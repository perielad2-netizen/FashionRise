/* FashionRise Web Push handlers — imported by the generated Workbox SW.
 * Keep this file free of HTML navigation fallbacks (CF Access SW safety).
 */
/* eslint-disable no-restricted-globals */

const ALLOWED_PUSH_PREFIXES = [
  '/studio',
  '/login',
  '/register',
  '/forgot-password',
  '/reset-password',
  '/verify-email',
  '/privacy',
]

function sanitizePushUrl(raw) {
  let url = typeof raw === 'string' && raw.trim() ? raw.trim() : '/studio/runway'
  try {
    if (/^https?:\/\//i.test(url)) {
      const u = new URL(url)
      if (u.hostname !== 'fashionrise.app' && u.hostname !== 'www.fashionrise.app') {
        return '/studio/runway'
      }
      url = `${u.pathname}${u.search}${u.hash}`
    }
  } catch {
    return '/studio/runway'
  }
  if (!url.startsWith('/')) return '/studio/runway'
  const path = url.split('?')[0].split('#')[0]
  const ok = ALLOWED_PUSH_PREFIXES.some(
    (p) => path === p || path.startsWith(`${p}/`),
  )
  return ok ? url : '/studio/runway'
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
