/**
 * Capacitor deep-link / cold-start routing for FashionRise-owned URLs.
 * Reuses Android Google OAuth handoff without weakening it.
 */
import { App } from '@capacitor/app'
import { handleAndroidGoogleOAuthReturn } from './googleOAuthReturn'
import { isNativeShell, nativePlatform } from './platform'
import { classifyFashionRiseUrl, navigateInApp } from './urlPolicy'

let installed = false

async function routeIncomingUrl(url: string): Promise<boolean> {
  const classified = classifyFashionRiseUrl(url)
  if (classified.kind === 'oauth_handoff') {
    if (nativePlatform() === 'android') {
      return handleAndroidGoogleOAuthReturn(classified.url)
    }
    return false
  }
  if (classified.kind === 'in_app') {
    navigateInApp(classified.path)
    return true
  }
  // external_ok / reject — do not pull into WebView from deep-link entry.
  return false
}

/**
 * Intercept in-document clicks on absolute fashionrise.app links so the shell
 * stays on the local SPA instead of loading the remote website in-WebView.
 */
function installClickGuard(): void {
  if (typeof document === 'undefined') return
  document.addEventListener(
    'click',
    (event) => {
      const target = event.target as Element | null
      const anchor = target?.closest?.('a[href]') as HTMLAnchorElement | null
      if (!anchor) return
      const href = anchor.getAttribute('href') || ''
      if (!href || href.startsWith('#') || href.startsWith('mailto:')) return
      const classified = classifyFashionRiseUrl(href)
      if (classified.kind !== 'in_app') return
      // Only rewrite absolute app-host links (relative Links already SPA).
      if (!/^https?:\/\//i.test(href)) return
      event.preventDefault()
      navigateInApp(classified.path)
    },
    true,
  )
}

export async function installNativeDeepLinkRouter(): Promise<void> {
  if (!isNativeShell() || installed) return
  installed = true
  installClickGuard()

  void App.addListener('appUrlOpen', ({ url }) => {
    void routeIncomingUrl(url)
  })

  try {
    const launch = await App.getLaunchUrl()
    if (launch?.url) {
      await routeIncomingUrl(launch.url)
    }
  } catch {
    /* no launch URL */
  }
}

/** Test helper — reset install guard between unit tests. */
export function _resetDeepLinkInstallForTests(): void {
  installed = false
}
