/**
 * Destinations allowed inside push notification payloads (Web Push + native).
 *
 * Never include password-reset, email-verification, or OAuth token URLs.
 * Deep-link / email flows use urlPolicy separately and may carry hash tokens.
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

export function isPushDestinationPath(pathname: string): boolean {
  const path = (pathname || '/').split('?')[0].split('#')[0] || '/'
  if (BLOCKED_PUSH_PATH_PREFIXES.some((p) => path === p || path.startsWith(p))) {
    return false
  }
  return PUSH_PATH_ALLOWLIST.some(
    (allowed) => path === allowed || path.startsWith(`${allowed}/`),
  )
}

/** Safe non-credential queries allowed on specific Studio paths (Manage friends). */
const ALLOWED_PUSH_QUERIES: ReadonlySet<string> = new Set(['/studio/fashionrise?friends=1'])

/** Safe SPA path for a push tap; defaults to FashionRise feed. Never returns credential-bearing URLs. */
export function sanitizePushDestination(raw: unknown): string {
  const fallback = '/studio/fashionrise'
  if (typeof raw !== 'string' || !raw.trim()) return fallback
  let url = raw.trim()
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
  if (!isPushDestinationPath(path)) return fallback
  if (path === '/') return fallback
  const query = (url.split('?')[1] || '').split('#')[0].trim()
  // Drop query/hash by default; allow only explicitly safe pairs.
  if (query) {
    const candidate = `${path}?${query}`
    if (ALLOWED_PUSH_QUERIES.has(candidate)) return candidate
  }
  return path
}
