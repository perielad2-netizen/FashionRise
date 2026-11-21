import { App } from '@capacitor/app'
import { Keyboard } from '@capacitor/keyboard'
import { StatusBar, Style } from '@capacitor/status-bar'
import { SplashScreen } from '@capacitor/splash-screen'
import { installNativeDeepLinkRouter } from './deepLinks'
import {
  isNativeFilePickerOpen,
  wasNativeFilePickerRecentlyOpen,
} from './filePickerGuard'
import {
  isNativeIosStarsShop,
  recoverPendingStarsPurchases,
  startIapTransactionUpdateRecovery,
} from './iap'
import { isNativeShell, nativePlatform } from './platform'
import { syncNativePushAfterAuth } from './nativePush'

/** Soften native chrome once the SPA mounts. Safe no-op on web. */
export async function bootstrapNativeShell(): Promise<void> {
  if (!isNativeShell()) return
  try {
    await StatusBar.setStyle({ style: Style.Dark })
    await StatusBar.setBackgroundColor({ color: '#090F1F' })
    // Edge-to-edge WebView; shell/modals already pad with env(safe-area-inset-*).
    // overlay:false + contentInset automatic left a blank strip under the status bar.
    await StatusBar.setOverlaysWebView({ overlay: true })
    document.documentElement.classList.add('fr-native-shell')
    const platform = nativePlatform()
    if (platform === 'android' || platform === 'ios') {
      document.documentElement.classList.add(`fr-native-${platform}`)
    }
    // iOS WKWebView form accessory (↑↓✓ black bar above keyboard) — hide it.
    // Android/web never show this chrome; Chat/Friends inputs looked broken on iOS.
    if (platform === 'ios') {
      await Keyboard.setAccessoryBarVisible({ isVisible: false })
    }
  } catch {
    /* web / unsupported */
  }
  try {
    await SplashScreen.hide()
  } catch {
    /* ignore */
  }
  void App.addListener('backButton', ({ canGoBack }) => {
    // Android Fitting Room: Back during CAMERA permission / capture must not
    // navigate or finish the Activity — that crashed and left a file-chooser loop.
    if (isNativeFilePickerOpen() || wasNativeFilePickerRecentlyOpen()) return
    if (canGoBack) {
      window.history.back()
      return
    }
    // Never App.exitApp() here — finishing MainActivity mid permission callback
    // caused "FashionRise keeps stopping" on the next Camera tap.
    void App.minimizeApp().catch(() => {
      /* ignore */
    })
  })

  // FashionRise-owned deep links + click guard (incl. Android Google OAuth handoff).
  void installNativeDeepLinkRouter()

  // Bounded Apple Stars recovery on resume (cooldown + credit gate inside recover).
  if (isNativeIosStarsShop()) {
    void startIapTransactionUpdateRecovery()
    void App.addListener('appStateChange', ({ isActive }) => {
      if (!isActive) return
      void recoverPendingStarsPurchases().catch(() => {
        /* ignore — shop UI surfaces recovery messaging */
      })
    })
  }

  // Native push is fail-closed until operator flags + FCM/APNs are ready.
  void syncNativePushAfterAuth().catch(() => {
    /* ignore — Runway UI surfaces unsupported/disabled */
  })
}
