/**
 * Central FashionRise-owned URL policy for Capacitor shells.
 *
 * FashionRise destinations stay in-app (SPA navigate). Google OAuth Custom Tabs,
 * mailto, WhatsApp, and store purchase flows remain intentional system handoffs.
 * Never follow unchecked external URLs into the WebView.
 */

export type UrlClass =
  | { kind: 'in_app'; path: string }
  | { kind: 'oauth_handoff'; url: string }
  | { kind: 'external_ok'; reason: 'mailto' | 'whatsapp' | 'http_external' }
  | { kind: 'reject'; reason: string }

const APP_HOSTS = new Set(['fashionrise.app', 'www.fashionrise.app'])
const NATIVE_SCHEME = 'app.fashionrise.studio'

/** SPA paths FashionRise may open from deep links / push taps (prefix match). */
export const IN_APP_PATH_ALLOWLIST: readonly string[] = [
  '/',
  '/login',
  '/register',
  '/forgot-password',
  '/reset-password',
  '/verify-email',
  '/privacy',
  '/auth/google/complete',
  '/studio',
]

export function isAllowedInAppPath(pathname: string): boolean {
  const path = normalizePath(pathname)
  return IN_APP_PATH_ALLOWLIST.some(
    (allowed) => path === allowed || (allowed !== '/' && path.startsWith(`${allowed}/`)),
  )
}

function normalizePath(pathname: string): string {
  const raw = (pathname || '/').trim() || '/'
  if (!raw.startsWith('/')) return `/${raw}`
  // Collapse duplicate slashes; keep trailing slash stripped except root.
  const collapsed = raw.replace(/\/{2,}/g, '/')
  if (collapsed.length > 1 && collapsed.endsWith('/')) return collapsed.slice(0, -1)
  return collapsed
}

/**
 * Classify a URL for native routing. Tokens in hash fragments are preserved on
 * in-app paths (reset/verify) — callers must not log the full URL.
 */
export function classifyFashionRiseUrl(raw: string): UrlClass {
  const input = (raw || '').trim()
  if (!input) return { kind: 'reject', reason: 'empty' }

  // Relative SPA path
  if (input.startsWith('/') && !input.startsWith('//')) {
    try {
      const u = new URL(input, 'https://fashionrise.app')
      if (!isAllowedInAppPath(u.pathname)) {
        return { kind: 'reject', reason: 'path_not_allowlisted' }
      }
      return { kind: 'in_app', path: `${u.pathname}${u.search}${u.hash}` }
    } catch {
      return { kind: 'reject', reason: 'bad_relative' }
    }
  }

  let parsed: URL
  try {
    parsed = new URL(input)
  } catch {
    return { kind: 'reject', reason: 'unparseable' }
  }

  const protocol = parsed.protocol.toLowerCase()

  if (protocol === 'mailto:') {
    return { kind: 'external_ok', reason: 'mailto' }
  }

  // Android Google OAuth one-time handoff (existing secure flow).
  if (protocol === `${NATIVE_SCHEME}:`) {
    const path = `${parsed.host}${parsed.pathname}`.replace(/\/+$/, '')
    if (path === 'auth/google/native' || input.toLowerCase().includes('auth/google/native')) {
      return { kind: 'oauth_handoff', url: input }
    }
    return { kind: 'reject', reason: 'unknown_native_scheme_path' }
  }

  if (protocol === 'http:' || protocol === 'https:') {
    const host = parsed.hostname.toLowerCase()
    if (APP_HOSTS.has(host)) {
      // Never treat API paths as SPA destinations.
      if (parsed.pathname.startsWith('/api/')) {
        return { kind: 'reject', reason: 'api_path_not_spa' }
      }
      if (!isAllowedInAppPath(parsed.pathname)) {
        return { kind: 'reject', reason: 'path_not_allowlisted' }
      }
      return { kind: 'in_app', path: `${parsed.pathname}${parsed.search}${parsed.hash}` }
    }
    // WhatsApp share helper
    if (host === 'wa.me' || host === 'api.whatsapp.com' || host.endsWith('.whatsapp.com')) {
      return { kind: 'external_ok', reason: 'whatsapp' }
    }
    return { kind: 'external_ok', reason: 'http_external' }
  }

  return { kind: 'reject', reason: `unsupported_protocol:${protocol}` }
}

/** Navigate in-SPA without exposing tokens to logs. */
export function navigateInApp(pathWithSearchHash: string): void {
  const classified = classifyFashionRiseUrl(
    pathWithSearchHash.startsWith('/') ? pathWithSearchHash : `/${pathWithSearchHash}`,
  )
  if (classified.kind !== 'in_app') return
  if (typeof window === 'undefined') return
  window.location.assign(classified.path)
}
