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
import {
  installNativePushInteractionListeners,
  syncNativePushAfterAuth,
} from './nativePush'
import { isNativeShell, nativePlatform } from './platform'

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
    // iOS WKWebView form accessory (↑↓✓ black bar above keyboard) — hide for
    // every text field (chat, friends, profile, techpack, auth, etc.).
    // Android/web never show this chrome. Re-assert on keyboard show in case
    // WKWebView restores the accessory after focus changes.
    if (platform === 'ios') {
      const hideAccessory = () => {
        void Keyboard.setAccessoryBarVisible({ isVisible: false }).catch(() => {
          /* unsupported */
        })
      }
      hideAccessory()
      void Keyboard.addListener('keyboardWillShow', hideAccessory)
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

  // Push tap listeners before auth — cold-start intents are retained/queued.
  void installNativePushInteractionListeners().catch(() => {
    /* plugin unavailable on web */
  })

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

  // Native push: auto-register when OS permission is granted and user has not
  // opted out (Settings is preference — not a second mandatory activation).
  // Retry safely on resume for transient FCM / network failures.
  void syncNativePushAfterAuth().catch(() => {
    /* ignore — Settings toggle surfaces unsupported/disabled */
  })
  void App.addListener('appStateChange', ({ isActive }) => {
    if (!isActive) return
    void syncNativePushAfterAuth().catch(() => {
      /* ignore — transient; next resume retries */
    })
  })
}
