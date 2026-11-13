/**
 * Android Google Sign-In return path.
 *
 * Custom Tabs completes OAuth on fashionrise.app; the server redirects to
 * ``app.fashionrise.studio://auth/google/native?code=…`` (one-time handoff).
 * We redeem the code for tokens over HTTPS — tokens never sit in the deep link.
 */
import { App } from '@capacitor/app'
import { Browser } from '@capacitor/browser'
import {
  completeGoogleOAuthSession,
  redeemGoogleNativeHandoff,
} from '@/services/auth/authApi'
import { isNativeShell, nativePlatform } from './platform'

const NATIVE_SCHEME = 'app.fashionrise.studio'
const NATIVE_HOST_PATH = '//auth/google/native'

let listening = false
let redeemInFlight: string | null = null

function safeNext(raw: string | null): string {
  const next = (raw || '/studio/home').trim()
  if (next.startsWith('/') && !next.startsWith('//')) return next
  return '/studio/home'
}

export function parseAndroidGoogleHandoffUrl(url: string): { code: string; next: string } | null {
  const trimmed = (url || '').trim()
  if (!trimmed) return null
  let parsed: URL
  try {
    parsed = new URL(trimmed)
  } catch {
    return null
  }
  if (parsed.protocol !== `${NATIVE_SCHEME}:`) return null
  // URL parser: host "auth", pathname "/google/native" for app.fashionrise.studio://auth/google/native
  const path = `${parsed.host}${parsed.pathname}`.replace(/\/+$/, '')
  if (path !== 'auth/google/native' && !trimmed.includes(NATIVE_HOST_PATH)) {
    // Accept either host/path split above or string contains check for older parsers.
    if (!trimmed.toLowerCase().includes('auth/google/native')) return null
  }
  const code = (parsed.searchParams.get('code') || '').trim()
  if (!code || code.length < 16) return null
  return { code, next: safeNext(parsed.searchParams.get('next')) }
}

async function closeAuthBrowser(): Promise<void> {
  try {
    await Browser.close()
  } catch {
    /* already closed */
  }
}

export async function handleAndroidGoogleOAuthReturn(url: string): Promise<boolean> {
  if (!(isNativeShell() && nativePlatform() === 'android')) return false
  const handoff = parseAndroidGoogleHandoffUrl(url)
  if (!handoff) return false
  if (redeemInFlight === handoff.code) return true
  redeemInFlight = handoff.code
  try {
    const tokens = await redeemGoogleNativeHandoff(handoff.code)
    await completeGoogleOAuthSession(tokens)
    await closeAuthBrowser()
    window.location.replace(handoff.next)
    return true
  } catch {
    await closeAuthBrowser()
    window.location.replace('/login?error=google_native_handoff_failed')
    return false
  } finally {
    redeemInFlight = null
  }
}

/** Open Google OAuth start URL in Custom Tabs (secure system browser). */
export async function openAndroidGoogleOAuth(startUrl: string): Promise<void> {
  await Browser.open({ url: startUrl, toolbarColor: '#090F1F' })
}

/** Register appUrlOpen + cold-start launch URL handlers (idempotent). */
export async function installAndroidGoogleOAuthReturnListener(): Promise<void> {
  if (!(isNativeShell() && nativePlatform() === 'android')) return
  if (listening) return
  listening = true

  void App.addListener('appUrlOpen', ({ url }) => {
    void handleAndroidGoogleOAuthReturn(url)
  })

  try {
    const launch = await App.getLaunchUrl()
    if (launch?.url) {
      void handleAndroidGoogleOAuthReturn(launch.url)
    }
  } catch {
    /* ignore */
  }
}
